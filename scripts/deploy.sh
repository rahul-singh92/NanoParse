
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CLUSTER="nanoParse-cluster"
MODEL_VERSION="${MODEL_VERSION:-v1}"
MODEL_DIR=".cache/models"

case "$MODEL_VERSION" in
  v1)
    MODEL_FILE="pythia-70m-v1.tar.gz"
    ;;
  v2)
    MODEL_FILE="pythia-70m-v2.tar.gz"
    ;;
  *)
    echo "Unsupported MODEL_VERSION: $MODEL_VERSION"
    exit 1
    ;;
esac

for cmd in docker k3d kubectl helm curl python3; do
  command -v "$cmd" >/dev/null || {
    echo "Missing required command: $cmd"
    exit 1
  }
done

docker info >/dev/null

echo "==> Creating cluster if necessary"
if ! k3d cluster list | grep -q "$CLUSTER"; then
  k3d cluster create --config cluster/k3d.yaml
fi

kubectl config use-context "k3d-$CLUSTER"
kubectl wait --for=condition=Ready nodes --all --timeout=180s

echo "==> Installing SeaweedFS"
helm repo add seaweedfs https://seaweedfs.github.io/seaweedfs/helm --force-update
helm repo update

kubectl create namespace data --dry-run=client -o yaml | kubectl apply -f -

if helm status seaweedfs -n data >/dev/null 2>&1; then
  helm upgrade seaweedfs seaweedfs/seaweedfs \
    --version 4.51.0 -n data -f cluster/seaweedfs-values.yaml \
    --timeout 15m --wait
else
  helm install seaweedfs seaweedfs/seaweedfs \
    --version 4.51.0 -n data -f cluster/seaweedfs-values.yaml \
    --timeout 15m --wait
fi

kubectl rollout status deployment/seaweedfs-s3 -n data --timeout=300s
kubectl rollout status statefulset/seaweedfs-master -n data --timeout=300s
kubectl rollout status statefulset/seaweedfs-volume -n data --timeout=300s
kubectl rollout status statefulset/seaweedfs-filer -n data --timeout=300s

echo "==> Downloading model release"
mkdir -p "$MODEL_DIR"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"

if [ ! -f "$MODEL_PATH" ]; then
  curl -fL \
    "https://github.com/rahul-singh92/NanoParse/releases/download/v1.0/$MODEL_FILE" \
    -o "$MODEL_PATH"
fi

echo "==> Starting temporary S3 port-forward"

S3_PORT=8334

if lsof -nP -iTCP:$S3_PORT -sTCP:LISTEN >/dev/null 2>&1; then
  S3_PORT=8335
fi

kubectl port-forward -n data svc/seaweedfs-s3 "$S3_PORT:8333" \
  > /tmp/nanoparse-s3-port-forward.log 2>&1 &
PF_PID=$!

cleanup() {
  kill "$PF_PID" 2>/dev/null || true
}
trap cleanup EXIT

for i in $(seq 1 30); do
  if curl -s "http://localhost:$S3_PORT/" >/dev/null; then
    break
  fi
  sleep 2
done

if ! kill -0 "$PF_PID" 2>/dev/null; then
  cat /tmp/nanoparse-s3-port-forward.log
  echo "S3 port-forward failed"
  exit 1
fi

echo "==> Preparing deployment Python environment"
if [ ! -x ".venv-deploy/bin/python" ]; then
  python3 -m venv .venv-deploy
fi

.venv-deploy/bin/python -m pip install --quiet boto3==1.38.18

echo "==> Uploading and verifying model"
S3_ENDPOINT="http://localhost:$S3_PORT" \
  .venv-deploy/bin/python scripts/upload_model.py \
    --file "$MODEL_PATH" \
    --version "$MODEL_VERSION"

echo "==> Creating application namespace and credentials"
kubectl create namespace app --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic seaweedfs-s3-credentials \
  -n app \
  --from-literal=access-key=anonymous \
  --from-literal=secret-key=anonymous \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Building application image"
docker build -t nanoparse-service:v1 service/
k3d image import nanoparse-service:v1 -c "$CLUSTER"

echo "==> Deploying NanoParse"
kubectl apply -f k8s/task4.yaml
kubectl rollout status deployment/nanoparse -n app --timeout=600s

echo "==> Deployment complete"
kubectl get pods -n data
kubectl get pods -n app
echo "API: http://localhost:8080/parse"
