# k8s manifests

Minimal manifests for kind/minikube. Production would split env-specific config
into kustomize overlays — left out for brevity.

```bash
# 1. build images locally
docker build -t ollive/chat-api:latest  -f apps/chat-api/Dockerfile  .
docker build -t ollive/ingestion:latest -f apps/ingestion/Dockerfile .
docker build -t ollive/web:latest       -f apps/web/Dockerfile       .

# 2. load into kind (if using kind)
kind load docker-image ollive/chat-api:latest ollive/ingestion:latest ollive/web:latest

# 3. apply
kubectl apply -f infra/k8s/namespace.yaml
kubectl create secret generic ollive-secrets -n ollive \
  --from-literal=OPENAI_API_KEY=$OPENAI_API_KEY \
  --from-literal=ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  --from-literal=GOOGLE_API_KEY=$GOOGLE_API_KEY \
  --dry-run=client -o yaml | kubectl apply -f -

# postgres init: replace the placeholder ConfigMap with the real init.sql
kubectl create configmap postgres-init -n ollive \
  --from-file=01-init.sql=infra/postgres/init.sql \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f infra/k8s/config.yaml
kubectl apply -f infra/k8s/postgres.yaml
kubectl apply -f infra/k8s/redis.yaml
kubectl apply -f infra/k8s/ingestion.yaml
kubectl apply -f infra/k8s/chat-api.yaml
kubectl apply -f infra/k8s/web.yaml
kubectl apply -f infra/k8s/observability.yaml

# 4. port-forward to test
kubectl -n ollive port-forward svc/web 3000:3000 &
kubectl -n ollive port-forward svc/chat-api 8000:8000 &
kubectl -n ollive port-forward svc/grafana 3001:3000 &
```
