import os
import json
from pathlib import Path

import requests

SHARD_INDEX = int(os.environ.get("SHARD_INDEX", "0"))
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", "2"))

OLLAMA_URL = os.environ.get(
    "OLLAMA_URL",
    "http://10.154.12.243:11434/api/generate"
)

S3_URL = os.environ.get(
    "S3_URL",
    "http://seaweedfs-s3.data.svc.cluster.local:8333"
)

MODEL = "phi3.5"
CHECKPOINT_DIR = Path("checkpoints")

def load_commands():
    # download the command dataset from seaweedfs
    url = f"{S3_URL}/datasets/commands_pool.jsonl"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    commands = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]

    return commands

def load_checkpoint():
    checkpoint_file = CHECKPOINT_DIR / f"shard-{SHARD_INDEX}.jsonl"

    if not checkpoint_file.exists():
        return []

    results = []
    seen_ids = set()

    commands = load_commands()
    selected_ids = {
        command["id"] for command in select_shard(commands)
    }

    with checkpoint_file.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            record = json.loads(line)

            if set(record.keys()) != {"id", "text", "teacher_raw"}:
                raise ValueError(
                    f"Invalid checkpoint keys at line {line_number}"
                )

            record_id = record["id"]

            if record_id not in selected_ids:
                raise ValueError(
                    f"ID {record_id} does not belong to worker {SHARD_INDEX}"
                )

            if record_id in seen_ids:
                raise ValueError(
                    f"Duplicate ID in checkpoint: {record_id}"
                )

            seen_ids.add(record_id)
            results.append(record)

    return results

def save_checkpoint(results):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    checkpoint_file = CHECKPOINT_DIR / f"shard-{SHARD_INDEX}.jsonl"

    with checkpoint_file.open("w", encoding="utf-8") as file:
        for record in results:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

def restore_checkpoint():
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    checkpoint_file = CHECKPOINT_DIR / f"shard-{SHARD_INDEX}.jsonl"

    url = f"{S3_URL}/datasets/teacher/shard-{SHARD_INDEX}.jsonl"

    response = requests.get(url, timeout=120)

    if response.status_code == 404:
        print("No remote checkpoint found. Starting fresh.")
        return

    response.raise_for_status()

    checkpoint_file.write_text(response.text, encoding="utf-8")

    print("Remote checkpoint restored successfully.")

def select_shard(commands):
    return [
        command
        for index, command in enumerate(commands)
        if index % SHARD_COUNT == SHARD_INDEX
    ]

def label_command(command, prompt):
    payload = {
        "model": MODEL,
        "prompt": prompt + "\n" + command["text"],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_predict": 100
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=180
    )

    response.raise_for_status()

    return response.json()["response"]

def main():
    if SHARD_COUNT <= 0 or not 0 <= SHARD_INDEX < SHARD_COUNT:
        raise ValueError("Invalid Shard Index or Shard Count")

    print(f"Starting worker {SHARD_INDEX}/{SHARD_COUNT}")

    prompt = Path("prompts/teacher_prompt.txt").read_text()

    commands = load_commands()
    selected = select_shard(commands)

    max_commands = int(os.environ.get("MAX_COMMANDS", "0"))

    if max_commands > 0:
        selected = selected[:max_commands]

    print(f"Total commands: {len(commands)}")
    print(f"Assigned commands: {len(selected)}")

    restore_checkpoint()
    results = load_checkpoint()

    completed_ids = {record["id"] for record in results}

    print(f"Previously completed: {len(completed_ids)}")

    for index, command in enumerate(selected, start=1):

        if command["id"] in completed_ids:
            continue

        raw_reply = label_command(command, prompt)

        record = {
            "id": command["id"],
            "text": command["text"],
            "teacher_raw": raw_reply
        }

        results.append(record)
        completed_ids.add(command["id"])

        print(
            f"Worker {SHARD_INDEX}: "
            f"{len(completed_ids)}/{len(selected)} completed",
            flush=True
        )

        if len(results) % 10 == 0:
            save_checkpoint(results)

            url = f"{S3_URL}/datasets/teacher/shard-{SHARD_INDEX}.jsonl"

            output = "\n".join(
                json.dumps(item, ensure_ascii=False)
                for item in results
            ) + "\n"

            response = requests.put(
                url, 
                data=output.encode("utf-8"),
                timeout=120
            )

            response.raise_for_status()

            print("Checkpoint uploaded to SeaweedFS")

    save_checkpoint(results)

    url = f"{S3_URL}/datasets/teacher/shard-{SHARD_INDEX}.jsonl"

    output = "\n".join(
        json.dumps(item, ensure_ascii=False)
        for item in results
    ) + "\n"

    response = requests.put(
        url, 
        data=output.encode("utf-8"),
        timeout=120
    )

    response.raise_for_status()

    print(f"Worker {SHARD_INDEX} completed successfully!")
    print(f"Uploaded results to {url}")

if __name__ == "__main__":
    main()
