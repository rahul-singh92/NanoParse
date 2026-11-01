import json
import os
import socket
import tarfile
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import boto3
import torch
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_URI = os.environ["MODEL_URI"]
MODEL_VERSION = os.environ["MODEL_VERSION"]
S3_ENDPOINT = os.environ["S3_ENDPOINT"]
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "100"))

FAULT_INJECT = os.environ.get("FAULT_INJECT", "0") == "1"
POD_NAME = os.environ.get("POD_NAME", socket.gethostname())

SCHEMA_PATH = Path("/app/schema.json")
MODEL_DIR = Path("/tmp/nanoparse-model")

ready = False
model = None
tokenizer = None
load_error = None
model_lock = threading.Lock()


class ParseRequest(BaseModel):
    text: str


def download_model():
    parsed = urlparse(MODEL_URI)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError("MODEL_URI must look like s3://bucket/object-key")

    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    # SeaweedFS currently has no authentication configured.
    # Kubernetes credentials can override these values when authentication is enabled.
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "anonymous")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "anonymous")

    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    archive = Path("/tmp/model.tar.gz")
    print(f"Downloading model from object storage: {MODEL_URI}", flush=True)
    s3.download_file(bucket, key, str(archive))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Reject unsafe archive paths.
    with tarfile.open(archive, "r:gz") as tar:
        root = MODEL_DIR.resolve()
        for member in tar.getmembers():
            target = (MODEL_DIR / member.name).resolve()
            if target != root and root not in target.parents:
                raise ValueError("Unsafe path in model archive")
        tar.extractall(MODEL_DIR)

    archive.unlink(missing_ok=True)


def load_model():
    global model, tokenizer, ready, load_error

    try:
        download_model()

        tokenizer = AutoTokenizer.from_pretrained(
            str(MODEL_DIR), local_files_only=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            str(MODEL_DIR),
            local_files_only=True,
            dtype=torch.float32,
        )
        model.to("cpu")
        model.eval()
        ready = True
        print(f"Model {MODEL_VERSION} loaded successfully", flush=True)

    except Exception as exc:
        load_error = str(exc)
        print(f"Model loading failed: {exc}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=load_model, daemon=True)
    thread.start()
    yield


app = FastAPI(lifespan=lifespan)


def validate_output(raw):
    try:
        result = json.loads(raw)
        schema = json.loads(SCHEMA_PATH.read_text())

        if not isinstance(result, dict):
            return None

        if set(result.keys()) != set(schema["keys"]):
            return None

        if result["intent"] not in schema["intents"]:
            return None

        for slot in ("date", "time", "place"):
            if result[slot] is not None and not isinstance(result[slot], str):
                return None

        return result
    except (ValueError, TypeError, KeyError):
        return None


def generate(text):
    prompt = f"Command: {text}\nJSON:"
    inputs = tokenizer(prompt, return_tensors="pt")

    with model_lock, torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


@app.get("/healthz")
def healthz():
    return {"status": "alive"}


@app.get("/readyz")
def readyz():
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready"},
        )
    return {"status": "ready"}


@app.post("/parse")
def parse(request: ParseRequest):
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"error": "model_not_ready"},
        )

    raw = "not json" if FAULT_INJECT else generate(request.text)
    result = validate_output(raw)

    headers = {
        "X-Model-Version": MODEL_VERSION,
        "X-Served-By": POD_NAME,
    }

    if result is None:
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_model_output"},
            headers=headers,
        )

    return JSONResponse(content=result, headers=headers)
