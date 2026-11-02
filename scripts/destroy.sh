
#!/usr/bin/env bash
set -Eeuo pipefail

CLUSTER="nanoParse-cluster"

echo "==> Removing NanoParse Kubernetes cluster"

if k3d cluster list | grep -q "$CLUSTER"; then
  k3d cluster delete "$CLUSTER"
  echo "Cluster deleted."
else
  echo "Cluster does not exist. Nothing to delete."
fi

echo "==> Cleanup complete"

