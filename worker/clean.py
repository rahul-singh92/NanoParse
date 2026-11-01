import json
import hashlib
import requests
from pathlib import Path
from collections import Counter

S3_URL = "http://localhost:8333"

SHARD_FILES = [
    "datasets/teacher/shard-0.jsonl",
    "datasets/teacher/shard-1.jsonl"
]

OUTPUT_DIR = Path("datasets/v1")

ALLOWED_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events"
}

REQUIRED_KEYS = {"intent", "date", "time", "place"}

def load_shards():
    records = []

    for shard_file in SHARD_FILES:
        url = f"{S3_URL}/{shard_file}"

        response = requests.get(url, timeout=120)
        response.raise_for_status()

        for line in response.text.splitlines():
            if line.strip():
                records.append(line)

    return records

def validate_record(record):
    try:
        data = json.loads(record["teacher_raw"])
    except (json.JSONDecodeError, TypeError):
        return None, "invalid_json"

    if not isinstance(data, dict) or set(data.keys()) != REQUIRED_KEYS:
        return None, "wrong_keys"

    if not isinstance(data["intent"], str) or data["intent"] not in ALLOWED_INTENTS:
        return None, "invalid_intent"

    for slot in ("date", "time", "place"):
        value = data[slot]

        if value is not None:
            if not isinstance(value, str) or value not in record["text"]:
                return None, "invalid_slot"

    return data, None

def remove_duplicates(records):
    unique_records = {}

    for record in records:
        command_id = record["id"]
        command_text = record["text"]

        if command_text not in unique_records:
            unique_records[command_text] = record
        else:
            existing_id = unique_records[command_text]["id"]

            if command_id < existing_id:
                unique_records[command_text] = record

    return list(unique_records.values())

def main():
    raw_records = load_shards()

    valid_records = []
    rejected = Counter()

    for line in raw_records:
        try:
            record = json.loads(line)

            if not isinstance(record, dict):
                rejected["wrong_keys"] += 1
                continue

            if set(record.keys()) != {"id", "text", "teacher_raw"}:
                rejected["wrong_keys"] += 1
                continue

            if not isinstance(record["id"], str) or not isinstance(record["text"], str):
                rejected["wrong_keys"] += 1
                continue

            parsed, error = validate_record(record)

            if error:
                rejected[error] += 1
                continue

            valid_records.append({
                "id": record["id"],
                "text": record["text"],
                **parsed
            })

        except json.JSONDecodeError:
            rejected["invalid_json"] += 1

    before_duplicates = len(valid_records)

    valid_records = remove_duplicates(valid_records)

    valid_records.sort(key=lambda record: record["id"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "train.jsonl"

    with output_file.open("w", encoding="utf-8") as file:
        for record in valid_records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    content = output_file.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()

    checksum_file = OUTPUT_DIR / "train.sha256"
    checksum_file.write_text(
        f"{checksum}  train.jsonl\n",
        encoding="utf-8"
    )

    duplicates = before_duplicates - len(valid_records)

    print("\nCleaning Report")
    print("-------------------------")
    print(f"Input records:       {len(raw_records)}")
    print(f"Invalid JSON:        {rejected['invalid_json']}")
    print(f"Wrong keys:          {rejected['wrong_keys']}")
    print(f"Invalid intent:      {rejected['invalid_intent']}")
    print(f"Invalid slot:        {rejected['invalid_slot']}")
    print(f"Duplicates removed:  {duplicates}")
    print(f"Records retained:    {len(valid_records)}")
    print("-------------------------")
    print(f"Output: {output_file}")
    print(f"SHA-256: {checksum}")

if __name__ == "__main__":
    main()