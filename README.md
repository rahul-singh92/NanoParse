# NanoParse

**NanoParse** is a lightweight natural-language command parser that converts user instructions into structured JSON. It uses knowledge distillation to fine-tune a compact Pythia-70M student model using teacher-generated training data, then serves the model through a containerised FastAPI application deployed on Kubernetes.

## Architecture

```text
Natural Language Input
        |
        v
   FastAPI Service
        |
        v
 Fine-tuned Pythia-70M
        |
        v
 JSON Validation
        |
        v
 Structured Response

Model Storage: SeaweedFS (S3-compatible)
Orchestration: Kubernetes (k3d)
Scaling: Horizontal Pod Autoscaler
Monitoring: Locust and kubectl metrics
```

## Technology Stack

- **Model:** EleutherAI/Pythia-70M
- **Teacher:** Ollama Phi-3.5
- **ML Framework:** PyTorch and Transformers
- **API:** FastAPI and Uvicorn
- **Object Storage:** SeaweedFS
- **Containerisation:** Docker
- **Orchestration:** Kubernetes using k3d
- **Deployment:** Helm
- **Load Testing:** Locust
- **CI/CD:** GitHub Actions and Gitleaks

## Repository Structure

| Directory | Purpose |
|---|---|
| `data/` | Validation data and schema |
| `datasets/` | Cleaned training datasets |
| `worker/` | Teacher generation and data cleaning |
| `training/` | Student model training configuration and scripts |
| `models/` | Model release metadata and local model artifacts |
| `service/` | FastAPI application and Dockerfile |
| `cluster/` | k3d and SeaweedFS configuration |
| `k8s/` | Kubernetes Deployment, Service, Ingress and HPA |
| `network/` | Subnet design and network ACL simulation |
| `tools/` | Evaluation, prediction, scoring and load-testing tools |
| `scripts/` | Deployment, teardown and model-upload scripts |
| `tests/` | Unit tests |
| `results/` | Experimental and assignment evidence |

## Requirements

- Docker
- k3d
- kubectl
- Helm
- Python 3.12 or compatible environment for the training and tooling workflow
- Make
- Locust for load testing

The deployment script creates `.venv-deploy` automatically for model-upload dependencies.

## Setup

Clone the repository:

```bash
git clone https://github.com/rahul-singh92/NanoParse.git
cd NanoParse
```

Create and activate a Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the service dependencies if running locally:

```bash
pip install -r service/requirements.txt
```

## Model Training

The student model is based on EleutherAI/Pythia-70M.

Training configuration:

- Maximum training samples: 1,500
- Epochs: 3
- Batch size: 4
- Learning rate: 0.00005
- Maximum sequence length: 256
- Optimisation: AdamW weight decay 0.01
- Execution device: CPU
- Random seed: 42

Train v1:

```bash
make train SUBSET=0 VERSION=v1
```

Train an experimental v2:

```bash
make train SUBSET=0 VERSION=v2
```

The optional `--data` argument can select a different training dataset:

```bash
python training/train.py --version v2 --data datasets/v2/train.jsonl
```

Training outputs are stored under `training/output/` and are excluded from Git.

## Evaluation

Generate predictions and evaluate the model using the provided tools:

```bash
python tools/score.py \
  results/student_predictions.jsonl \
  data/validation.jsonl \
  --out results/student_validation.json
```

The evaluator measures:

- JSON validity
- Intent accuracy
- Date accuracy
- Time accuracy
- Place accuracy
- Full-frame accuracy

## Deployment

Deploy the production v1 model:

```bash
make up MODEL_VERSION=v1
```

Deploy the experimental v2 model:

```bash
make up MODEL_VERSION=v2
```

The deployment script:

1. Creates the k3d cluster if required.
2. Installs SeaweedFS through Helm.
3. Downloads the selected model archive from the GitHub Release.
4. Uploads the model to S3-compatible storage.
5. Builds and imports the application Docker image.
6. Deploys the Kubernetes resources.
7. Waits for the application rollout.

API endpoint:

```text
http://localhost:8080/parse
```

## API Usage

Send a POST request:

```bash
curl -X POST http://localhost:8080/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"Set an alarm for 7 am"}'
```

The service returns structured JSON containing:

```json
{
  "intent": "alarm_set",
  "date": null,
  "time": "seven am",
  "place": null
}
```

The exact prediction depends on model output.

Health endpoints:

- `GET /healthz` — process health
- `GET /readyz` — model readiness
- `POST /parse` — command parsing

Successful responses include `X-Model-Version` and `X-Served-By` headers.

## Kubernetes and Load Testing

The Kubernetes deployment uses two replicas during the assignment load test, with an HPA configured for CPU-based scaling.

Run the standard Locust test:

```bash
locust -f tools/locustfile.py \
  --headless \
  --users 4 \
  --spawn-rate 4 \
  --run-time 2m \
  --host http://localhost:8080 \
  --csv results/task7/loadtest
```

Monitor resource utilisation:

```bash
kubectl top pods -n app
```

Inspect the deployment:

```bash
kubectl get pods -n app
kubectl get services -n app
kubectl get hpa -n app
```

## Network Configuration

The `network/` directory contains:

- Subnet allocation and CIDR design
- Inbound and outbound network ACL rules
- ACL explanation
- Sample packets for simulation

Run the ACL tests:

```bash
python tools/nacl_sim.py \
  network/nacl.json \
  network/packets_sample.jsonl \
  --check
```

## Automated Testing and CI

GitHub Actions runs the following stages:

1. Python compilation and Ruff lint checks
2. Unit tests
3. Model evaluation using the released v1 artifact
4. Gitleaks secret scanning

The manual workflow also supports evaluation of an untrained model and enforces a 95% JSON-validity quality gate.

Run unit tests locally:

```bash
python -m unittest discover -s tests -v
```

## Experimental Results

The production v1 model achieved the following validation results:

| Metric | Result |
|---|---:|
| JSON validity | 90% |
| Intent accuracy | 75% |
| Date accuracy | 68% |
| Time accuracy | 76% |
| Place accuracy | 77% |
| Full-frame accuracy | 41% |

A separate v2 experiment achieved 89% JSON validity and 42% full-frame accuracy. V1 remains the deployed production version.

### Task 7 Load Test

Standard two-minute Locust test using four concurrent users:

| Metric | Result |
|---|---:|
| Requests | 89 |
| Successful requests | 78 |
| Failed requests | 11 |
| Error rate | 12.36% |
| Median latency | 3,700 ms |
| p95 latency | 16,000 ms |
| Throughput | 0.748 requests/sec |

The two replicas served 41 and 37 successful requests respectively.

The measured p95 latency and error rate do not meet the assignment targets of 5 seconds and 1%. Resource samples showed CPU peaks close to 1 core per pod, while peak memory remained below 560 MiB per pod.

These results are reported as measured, not as performance targets achieved.

## Model Artifact

Model archives are distributed through the GitHub Release rather than committed to the repository.

Release: [NanoParse v1.0](https://github.com/rahul-singh92/NanoParse/releases/tag/v1.0)

The deployment and CI workflows verify the v1 model archive checksum before use.

## AI Use and Responsible Development

See [AI_USE.md](AI_USE.md) for details about AI-assisted development, teacher-generated data, human oversight, validation and known limitations.

## Cleanup

Delete the local Kubernetes cluster and its resources:

```bash
make down
```

## Limitations and Future Improvements

- Improve JSON validity and full-frame prediction accuracy.
- Reduce CPU inference latency and improve throughput.
- Improve reliability under concurrent requests.
- Evaluate multi-node Kubernetes deployment and replicated storage.
- Expand validation coverage and test recovery under failure conditions.
- Use production-grade secret management and TLS for external deployment.
