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

.PHONY: help lint deploy status e2e undeploy build-images import-images restart-apps fix-images logs-user logs-product logs-order logs-all logs-since import-images-remote deploy-remote fix-images-remote neon-plan neon-apply neon-destroy k3s-spot-plan k3s-spot-apply k3s-spot-destroy db-format db-validate db-generate db-migrate-status db-migrate-all concurrency-smoke concurrency-idempotency-lite concurrency-hotspot-10tps concurrency-baseline concurrency-stress100 concurrency-stress200 concurrency-hotspot require-tf-remote-state

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
>echo "  make db-format             # Format all flashsale Prisma schemas"
>echo "  make db-validate           # Validate all flashsale Prisma schemas"
>echo "  make db-generate           # Generate Python Prisma client for the shared flashsale DB"
>echo "  make db-migrate-status     # Show Prisma migration status for the shared flashsale DB"
>echo "  make db-migrate-all        # Apply Prisma migrations to the shared flashsale DB"
>echo "  make concurrency-smoke     # 10 TPS non-hotspot smoke"
>echo "  make concurrency-idempotency-lite # Replay duplicate orders and verify dedupe"
>echo "  make concurrency-hotspot-10tps # 10 TPS single-product hotspot lane"
>echo "  make concurrency-baseline  # 50 TPS sustained baseline"
>echo "  make concurrency-stress100 # 100 TPS stress stage"
>echo "  make concurrency-stress200 # 200 TPS stress stage"
>echo "  make concurrency-hotspot   # High-conflict hotspot correctness test"
>echo "  make neon-plan             # terraform plan for Neon using remote S3 state"
>echo "  make neon-apply            # Provision Neon DB and write K8s secret"
>echo "  make neon-destroy          # Destroy Neon resources (caution: data loss)"
>echo "  make k3s-spot-plan         # terraform plan for the AWS spot k3s worker stack using remote S3 state"
>echo "  make k3s-spot-apply        # create or reconcile one self-healing AWS spot worker"
>echo "  make k3s-spot-destroy      # tear down the AWS spot k3s worker stack"

lint:
>cd application/flashsale && uv run pre-commit run --all-files

concurrency-smoke concurrency-idempotency-lite concurrency-hotspot-10tps concurrency-baseline concurrency-stress100 concurrency-stress200 concurrency-hotspot:
>$(MAKE) -C application/flashsale $@

db-format db-validate db-generate db-migrate-status db-migrate-all:
>$(MAKE) -C application/flashsale $@

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
>KUBECONFIG_PATH=$(KUBECONFIG_PATH) NAMESPACE=$(NAMESPACE) bash ./application/flashsale/scripts/e2e-smoke.sh

build-images:
>$(CONTAINER_CLI) build -t flashsales/user-service:$(IMAGE_TAG) application/flashsale/user-service
>$(CONTAINER_CLI) build -t flashsales/product-service:$(IMAGE_TAG) application/flashsale/product-service
>$(CONTAINER_CLI) build -t flashsales/order-service:$(IMAGE_TAG) application/flashsale/order-service

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
TERRAFORM_FLASHSALE_DIR ?= terraform/flashsale
TERRAFORM_K3S_NETWORK_DIR ?= terraform/k3s-spot-network
TERRAFORM_K3S_SPOT_DIR ?= terraform/k3s-spot-node
AWS_REGION ?=
TF_STATE_BUCKET ?=

define terraform_init_remote
terraform init \
	-backend-config="bucket=$(TF_STATE_BUCKET)" \
	-backend-config="key=$(1)" \
	-backend-config="region=$(AWS_REGION)" \
	-backend-config="encrypt=true"
endef

require-tf-remote-state:
>if [ -z "$(TF_STATE_BUCKET)" ]; then \
>  echo "TF_STATE_BUCKET is required. Local Terraform state is not supported in this repo."; \
>  exit 1; \
>fi
>if [ -z "$(AWS_REGION)" ]; then \
>  echo "AWS_REGION is required for remote S3 backend init."; \
>  exit 1; \
>fi

neon-plan: require-tf-remote-state
>cd $(TERRAFORM_NEON_DIR) && $(call terraform_init_remote,flashsales/neon/terraform.tfstate) && terraform plan

neon-apply: require-tf-remote-state
>cd $(TERRAFORM_NEON_DIR) && $(call terraform_init_remote,flashsales/neon/terraform.tfstate) && terraform apply

neon-destroy: require-tf-remote-state
>cd $(TERRAFORM_NEON_DIR) && $(call terraform_init_remote,flashsales/neon/terraform.tfstate) && terraform destroy

flashsale-plan: require-tf-remote-state
>cd $(TERRAFORM_FLASHSALE_DIR) && $(call terraform_init_remote,flashsales/terraform.tfstate) && terraform plan

flashsale-apply: require-tf-remote-state
>cd $(TERRAFORM_FLASHSALE_DIR) && $(call terraform_init_remote,flashsales/terraform.tfstate) && terraform apply

flashsale-destroy: require-tf-remote-state
>cd $(TERRAFORM_FLASHSALE_DIR) && $(call terraform_init_remote,flashsales/terraform.tfstate) && terraform destroy

k3s-network-plan: require-tf-remote-state
>cd $(TERRAFORM_K3S_NETWORK_DIR) && $(call terraform_init_remote,k3s/spot-network/terraform.tfstate) && terraform plan

k3s-network-apply: require-tf-remote-state
>cd $(TERRAFORM_K3S_NETWORK_DIR) && $(call terraform_init_remote,k3s/spot-network/terraform.tfstate) && terraform apply

k3s-network-destroy: require-tf-remote-state
>cd $(TERRAFORM_K3S_NETWORK_DIR) && $(call terraform_init_remote,k3s/spot-network/terraform.tfstate) && terraform destroy

k3s-spot-plan: require-tf-remote-state
>cd $(TERRAFORM_K3S_SPOT_DIR) && $(call terraform_init_remote,k3s/spot-node/terraform.tfstate) && terraform plan

k3s-spot-apply: require-tf-remote-state
>cd $(TERRAFORM_K3S_SPOT_DIR) && $(call terraform_init_remote,k3s/spot-node/terraform.tfstate) && terraform apply

k3s-spot-destroy: require-tf-remote-state
>cd $(TERRAFORM_K3S_SPOT_DIR) && $(call terraform_init_remote,k3s/spot-node/terraform.tfstate) && terraform destroy
