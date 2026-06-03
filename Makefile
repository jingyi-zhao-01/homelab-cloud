.RECIPEPREFIX := >

KUBECONFIG_PATH ?= .kube-config
NAMESPACE ?= flashsales
RELEASE ?= flashsales
CHART_PATH ?= charts/flashsales
IMAGE_TAG ?= latest
CONTAINER_CLI ?= docker
SSH_USER ?= root
SSH_HOST ?= 76.13.108.14
SSH_PORT ?= 22
REMOTE_K3S_CMD ?= k3s ctr images import -
SSH ?= ssh -p $(SSH_PORT) $(SSH_USER)@$(SSH_HOST)

.PHONY: help lint deploy status e2e undeploy build-images import-images restart-apps fix-images logs-user logs-product logs-order logs-all logs-since import-images-remote deploy-remote fix-images-remote neon-init neon-apply neon-destroy concurrency-smoke concurrency-idempotency-lite concurrency-baseline concurrency-stress100 concurrency-stress200 concurrency-hotspot

TAIL ?= 200
SINCE ?= 10m

help:
>echo "Targets:"
>echo "  make lint      # Run repo lint and shared pylint checks"
>echo "  make deploy    # Deploy chart to local k3s"
>echo "  make status    # Show pods and services"
>echo "  make e2e       # Run E2E smoke test"
>echo "  make undeploy  # Remove release"
>echo "  make build-images   # Build app images locally"
>echo "  make import-images  # Import images into k3s containerd (sudo required)"
>echo "  make restart-apps   # Restart app deployments"
>echo "  make fix-images     # Build + import + restart + status"
>echo "  make logs-user      # Stream user-service logs"
>echo "  make logs-product   # Stream product-service logs"
>echo "  make logs-order     # Stream order-service logs"
>echo "  make logs-all       # Show recent logs for all services"
>echo "  make logs-since     # Show logs in time window (SINCE=10m, TAIL=200)"
>echo "  make import-images-remote  # Stream local images into remote k3s containerd via SSH"
>echo "  make deploy-remote         # Deploy chart to remote cluster using .kube-config"
>echo "  make fix-images-remote     # Build + import to remote + restart + status"
>echo "  make concurrency-smoke     # 10 TPS, strict latency and zero 5xx"
>echo "  make concurrency-idempotency-lite # Replay duplicate orders and verify dedupe"
>echo "  make concurrency-baseline  # 50 TPS sustained baseline"
>echo "  make concurrency-stress100 # 100 TPS stress stage"
>echo "  make concurrency-stress200 # 200 TPS stress stage"
>echo "  make concurrency-hotspot   # High-conflict hotspot correctness test"
>echo "  make neon-init             # terraform init for Neon provider"
>echo "  make neon-apply            # Provision Neon DB and write K8s secret"
>echo "  make neon-destroy          # Destroy Neon resources (caution: data loss)"

lint:
>cd flashsale && uv run pre-commit run --all-files

concurrency-smoke concurrency-idempotency-lite concurrency-baseline concurrency-stress100 concurrency-stress200 concurrency-hotspot:
>$(MAKE) -C flashsale $@

check-local:
>API_SERVER=$$(KUBECONFIG=$(KUBECONFIG_PATH) kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'); \
>if ! [[ "$$API_SERVER" == *"localhost"* || "$$API_SERVER" == *"127.0.0.1"* ]]; then \
>  echo "Refusing deploy to non-local cluster: $$API_SERVER"; \
>  echo "This project is local-only. Set KUBECONFIG_PATH to a local k3s kubeconfig."; \
>  exit 1; \
>fi

deploy: check-local
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | KUBECONFIG=$(KUBECONFIG_PATH) kubectl apply -f -
>KUBECONFIG=$(KUBECONFIG_PATH) helm upgrade --install $(RELEASE) $(CHART_PATH) -n $(NAMESPACE)
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl get pods -n $(NAMESPACE)

status:
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl get pods -n $(NAMESPACE)
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl get svc -n $(NAMESPACE)

undeploy:
>KUBECONFIG=$(KUBECONFIG_PATH) helm uninstall $(RELEASE) -n $(NAMESPACE) || true


e2e: check-local
>KUBECONFIG_PATH=$(KUBECONFIG_PATH) NAMESPACE=$(NAMESPACE) bash ./flashsale/scripts/e2e-smoke.sh

build-images:
>$(CONTAINER_CLI) build -t flashsales/user-service:$(IMAGE_TAG) flashsale/user-service
>$(CONTAINER_CLI) build -t flashsales/product-service:$(IMAGE_TAG) flashsale/product-service
>$(CONTAINER_CLI) build -t flashsales/order-service:$(IMAGE_TAG) flashsale/order-service

import-images:
>$(CONTAINER_CLI) save flashsales/user-service:$(IMAGE_TAG) | sudo k3s ctr images import -
>$(CONTAINER_CLI) save flashsales/product-service:$(IMAGE_TAG) | sudo k3s ctr images import -
>$(CONTAINER_CLI) save flashsales/order-service:$(IMAGE_TAG) | sudo k3s ctr images import -

restart-apps:
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl rollout restart deployment/flashsales-user-service -n $(NAMESPACE)
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl rollout restart deployment/flashsales-product-service -n $(NAMESPACE)
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl rollout restart deployment/flashsales-order-service -n $(NAMESPACE)

fix-images: build-images import-images restart-apps status

import-images-remote:
>$(CONTAINER_CLI) save flashsales/user-service:$(IMAGE_TAG) | $(SSH) "$(REMOTE_K3S_CMD)"
>$(CONTAINER_CLI) save flashsales/product-service:$(IMAGE_TAG) | $(SSH) "$(REMOTE_K3S_CMD)"
>$(CONTAINER_CLI) save flashsales/order-service:$(IMAGE_TAG) | $(SSH) "$(REMOTE_K3S_CMD)"

deploy-remote:
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | KUBECONFIG=$(KUBECONFIG_PATH) kubectl apply -f -
>KUBECONFIG=$(KUBECONFIG_PATH) helm upgrade --install $(RELEASE) $(CHART_PATH) -n $(NAMESPACE)
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl get pods -n $(NAMESPACE)

fix-images-remote: build-images import-images-remote restart-apps status

logs-user:
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-user-service -f --tail=$(TAIL)

logs-product:
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-product-service -f --tail=$(TAIL)

logs-order:
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-order-service -f --tail=$(TAIL)

logs-all:
>echo "=== user-service ==="
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-user-service --tail=$(TAIL)
>echo "=== product-service ==="
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-product-service --tail=$(TAIL)
>echo "=== order-service ==="
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-order-service --tail=$(TAIL)

logs-since:
>echo "=== user-service (since $(SINCE)) ==="
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-user-service --since=$(SINCE) --tail=$(TAIL)
>echo "=== product-service (since $(SINCE)) ==="
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-product-service --since=$(SINCE) --tail=$(TAIL)
>echo "=== order-service (since $(SINCE)) ==="
>KUBECONFIG=$(KUBECONFIG_PATH) kubectl logs -n $(NAMESPACE) deploy/flashsales-order-service --since=$(SINCE) --tail=$(TAIL)

TERRAFORM_NEON_DIR ?= terraform/neon

neon-init:
>cd $(TERRAFORM_NEON_DIR) && terraform init

neon-apply:
>cd $(TERRAFORM_NEON_DIR) && terraform apply

neon-destroy:
>cd $(TERRAFORM_NEON_DIR) && terraform destroy
