import os
import csv
import json
import random
import argparse
from pathlib import Path

import yaml
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForCausalLM


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "training" / "config.yaml"


def set_seed(seed):
    random.seed(seed)
    torch.manual_seed(seed)


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def load_records(config, subset):
    dataset_path = ROOT / config["train_file"]
    records = []

    with open(dataset_path, "r") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
            if len(records) >= min(
                subset if subset else config["max_train_samples"],
                config["max_train_samples"]
            ):
                break

    if not records:
        raise ValueError("Training dataset is empty.")

    return records


def build_example(record):
    command = record["text"]

    target = {
        "intent": record["intent"],
        "date": record["date"],
        "time": record["time"],
        "place": record["place"]
    }

    prompt = f"Command: {command}\nJSON:"
    response = " " + json.dumps(target, separators=(",", ":"), ensure_ascii=False)

    return prompt, response


class CommandDataset(Dataset):
    def __init__(self, records, tokenizer, max_length):
        self.examples = []

        for record in records:
            prompt, response = build_example(record)

            prompt_ids = tokenizer(
                prompt,
                add_special_tokens=True,
                truncation=True,
                max_length=max_length
            )["input_ids"]

            response_ids = tokenizer(
                response,
                add_special_tokens=False
            )["input_ids"]

            eos_id = tokenizer.eos_token_id
            input_ids = prompt_ids + response_ids + [eos_id]

            if len(input_ids) > max_length:
                input_ids = input_ids[:max_length]

            labels = [-100] * len(prompt_ids)
            labels += response_ids + [eos_id]
            labels = labels[:len(input_ids)]

            # Ignore examples where truncation removed the entire target.
            if any(token != -100 for token in labels):
                self.examples.append((input_ids, labels))

        if not self.examples:
            raise ValueError("No usable training examples after tokenization.")

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, index):
        return self.examples[index]


def collate_batch(batch, pad_token_id):
    max_length = max(len(item[0]) for item in batch)

    input_ids = []
    attention_masks = []
    labels = []

    for ids, target_labels in batch:
        padding = max_length - len(ids)

        input_ids.append(ids + [pad_token_id] * padding)
        attention_masks.append([1] * len(ids) + [0] * padding)
        labels.append(target_labels + [-100] * padding)

    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "attention_mask": torch.tensor(attention_masks, dtype=torch.long),
        "labels": torch.tensor(labels, dtype=torch.long)
    }


def train():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", type=int, default=0)
    parser.add_argument("--version", default="v1")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    config = load_config()
    seed = args.seed if args.seed is not None else config["seed"]
    set_seed(seed)

    device = torch.device("cpu")

    print("Loading training records...")
    records = load_records(config, args.subset)
    print(f"Records loaded: {len(records)}")

    print(f"Loading tokenizer and model: {config['model_name']}")
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        config["model_name"],
        dtype=torch.float32
    )
    model.to(device)
    model.train()

    dataset = CommandDataset(
        records,
        tokenizer,
        config["max_seq_length"]
    )

    loader_generator = torch.Generator()
    loader_generator.manual_seed(seed)

    loader = DataLoader(
        dataset,
        batch_size=config["batch_size"],
        shuffle=True,
        generator=loader_generator,
        collate_fn=lambda batch: collate_batch(
            batch, tokenizer.pad_token_id
        )
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["learning_rate"],
        weight_decay=config["weight_decay"]
    )

    output_dir = ROOT / "training" / "output" / args.version
    output_dir.mkdir(parents=True, exist_ok=True)

    loss_path = ROOT / "training" / (
        "loss.csv" if args.version == "v1"
        else f"loss_{args.version}.csv"
    )

    with open(loss_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["epoch", "average_loss"])

        for epoch in range(config["epochs"]):
            total_loss = 0.0
            batches = 0

            for batch in loader:
                batch = {
                    key: value.to(device)
                    for key, value in batch.items()
                }

                optimizer.zero_grad()

                outputs = model(**batch)
                loss = outputs.loss

                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(), max_norm=1.0
                )
                optimizer.step()

                total_loss += loss.item()
                batches += 1

            average_loss = total_loss / batches
            writer.writerow([epoch + 1, average_loss])
            csvfile.flush()

            print(
                f"Epoch {epoch + 1}/{config['epochs']} "
                f"- Loss: {average_loss:.6f}"
            )

    print("Saving model and tokenizer...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    print(f"Training complete. Model saved to: {output_dir}")
    print(f"Loss history saved to: {loss_path}")


if __name__ == "__main__":
    train()
