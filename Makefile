# =============================================================================
# Piasecki Aerospace Skills Showcase — Makefile
# =============================================================================
#
# Usage: make [target]
# Run 'make help' to see all available targets.
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# --- Configuration -----------------------------------------------------------
PROJECT_NAME    := piasecki-demo
COMPOSE_FILE    := podman-compose.yml
K8S_DIR         := k8s
K3D_CLUSTER     := piasecki-demo
PYTHON          := python3
PIP             := pip3
CMAKE           := cmake
REDIS_PORT      := 6379

# Service ports
PORTAL_PORT     := 8080
GCS_PORT        := 8001
SIM_PORT        := 8002
ANALYSIS_PORT   := 8003
HARDWARE_PORT   := 8004

# Container image registry/prefix
IMAGE_PREFIX    := localhost/$(PROJECT_NAME)
IMAGE_TAG       := latest

# Service list
SERVICES := portal gcs simulation data-analysis hardware-integration

# Colors for help menu
CYAN  := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED   := \033[31m
BOLD  := \033[1m
RESET := \033[0m

# =============================================================================
# HELP
# =============================================================================

.PHONY: help
help: ## Show this help menu
	@echo ""
	@echo "$(BOLD)$(CYAN)╔══════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(BOLD)$(CYAN)║     Piasecki Aerospace Skills Showcase — Build System       ║$(RESET)"
	@echo "$(BOLD)$(CYAN)╚══════════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(BOLD)Usage:$(RESET) make $(GREEN)<target>$(RESET)"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} \
		/^[a-zA-Z0-9_-]+:.*?## / { \
			if ($$1 ~ /^#/) next; \
			printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2 \
		} \
		/^## / { \
			gsub(/^## /, "", $$0); \
			printf "\n$(BOLD)$(YELLOW)%s$(RESET)\n", $$0 \
		}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(BOLD)Service Ports:$(RESET)"
	@echo "  Portal .............. $(CYAN)http://localhost:$(PORTAL_PORT)$(RESET)"
	@echo "  Ground Control ...... $(CYAN)http://localhost:$(GCS_PORT)$(RESET)"
	@echo "  Simulation .......... $(CYAN)http://localhost:$(SIM_PORT)$(RESET)"
	@echo "  Data Analysis ....... $(CYAN)http://localhost:$(ANALYSIS_PORT)$(RESET)"
	@echo "  Hardware Integration  $(CYAN)http://localhost:$(HARDWARE_PORT)$(RESET)"
	@echo ""

# =============================================================================
## C Library (libs/flight-compute)
# =============================================================================

.PHONY: build-c
build-c: ## Build the MISRA-style C flight-compute library
	@echo "$(BOLD)$(GREEN)▶ Building C flight-compute library...$(RESET)"
	@mkdir -p libs/flight-compute/build
	@cd libs/flight-compute/build && $(CMAKE) .. && $(MAKE)
	@echo "$(GREEN)✓ C library built successfully$(RESET)"

.PHONY: test-c
test-c: build-c ## Run C library unit tests
	@echo "$(BOLD)$(GREEN)▶ Running C library tests...$(RESET)"
	@cd libs/flight-compute/build && ctest --output-on-failure
	@echo "$(GREEN)✓ C tests passed$(RESET)"

.PHONY: clean-c
clean-c: ## Clean C library build artifacts
	@echo "$(YELLOW)▶ Cleaning C build artifacts...$(RESET)"
	@rm -rf libs/flight-compute/build
	@echo "$(GREEN)✓ C artifacts cleaned$(RESET)"

# =============================================================================
## Python Shared Library (libs/common-py)
# =============================================================================

.PHONY: install-common
install-common: ## Install shared Python package in editable mode
	@echo "$(BOLD)$(GREEN)▶ Installing piasecki_common package...$(RESET)"
	@$(PIP) install -e libs/common-py/
	@echo "$(GREEN)✓ piasecki_common installed$(RESET)"

# =============================================================================
## Local Development
# =============================================================================

.PHONY: setup
setup: install-common build-c ## Set up local development environment (Python + C)
	@echo "$(BOLD)$(GREEN)▶ Installing service dependencies...$(RESET)"
	@for svc in $(SERVICES); do \
		if [ -f services/$$svc/requirements.txt ]; then \
			echo "  Installing $$svc dependencies..."; \
			$(PIP) install -r services/$$svc/requirements.txt; \
		fi; \
	done
	@echo "$(GREEN)✓ Development environment ready$(RESET)"

.PHONY: run-portal
run-portal: ## Run portal service locally (port 8080)
	@cd services/portal && FLASK_APP=app.py flask run --port $(PORTAL_PORT)

.PHONY: run-gcs
run-gcs: ## Run GCS service locally (port 8001)
	@cd services/gcs && FLASK_APP=app.py flask run --port $(GCS_PORT)

.PHONY: run-sim
run-sim: ## Run simulation service locally (port 8002)
	@cd services/simulation && FLASK_APP=app.py flask run --port $(SIM_PORT)

.PHONY: run-analysis
run-analysis: ## Run data analysis service locally (port 8003)
	@cd services/data-analysis && FLASK_APP=app.py flask run --port $(ANALYSIS_PORT)

.PHONY: run-hardware
run-hardware: ## Run hardware integration service locally (port 8004)
	@cd services/hardware-integration && FLASK_APP=app.py flask run --port $(HARDWARE_PORT)

.PHONY: run-redis
run-redis: ## Start a local Redis server
	@echo "$(BOLD)$(GREEN)▶ Starting Redis on port $(REDIS_PORT)...$(RESET)"
	@redis-server --port $(REDIS_PORT) --daemonize yes
	@echo "$(GREEN)✓ Redis running on port $(REDIS_PORT)$(RESET)"

# =============================================================================
## Testing & Linting
# =============================================================================

.PHONY: test
test: test-c test-python ## Run all tests (C + Python)

.PHONY: test-python
test-python: ## Run Python tests with pytest
	@echo "$(BOLD)$(GREEN)▶ Running Python tests...$(RESET)"
	@$(PYTHON) -m pytest services/ libs/common-py/ -v --tb=short
	@echo "$(GREEN)✓ Python tests passed$(RESET)"

.PHONY: lint
lint: ## Run linters (ruff for Python, cppcheck for C)
	@echo "$(BOLD)$(GREEN)▶ Linting Python code...$(RESET)"
	@$(PYTHON) -m ruff check services/ libs/common-py/ || true
	@echo "$(BOLD)$(GREEN)▶ Linting C code...$(RESET)"
	@cppcheck --enable=all --std=c11 libs/flight-compute/src/ libs/flight-compute/include/ 2>&1 || true
	@echo "$(GREEN)✓ Linting complete$(RESET)"

.PHONY: format
format: ## Auto-format Python code with ruff
	@echo "$(BOLD)$(GREEN)▶ Formatting Python code...$(RESET)"
	@$(PYTHON) -m ruff format services/ libs/common-py/
	@echo "$(GREEN)✓ Formatting complete$(RESET)"

# =============================================================================
## Container Build (Podman)
# =============================================================================

.PHONY: build
build: ## Build all service container images
	@echo "$(BOLD)$(GREEN)▶ Building all container images...$(RESET)"
	@for svc in $(SERVICES); do \
		echo "$(CYAN)  Building $$svc...$(RESET)"; \
		podman build -t $(IMAGE_PREFIX)-$$svc:$(IMAGE_TAG) -f services/$$svc/Containerfile .; \
	done
	@echo "$(GREEN)✓ All images built$(RESET)"

.PHONY: build-%
build-%: ## Build a specific service image (e.g., make build-portal)
	@echo "$(BOLD)$(GREEN)▶ Building $*...$(RESET)"
	@podman build -t $(IMAGE_PREFIX)-$*:$(IMAGE_TAG) -f services/$*/Containerfile .
	@echo "$(GREEN)✓ $* image built$(RESET)"

.PHONY: images
images: ## List all project container images
	@podman images --filter "reference=$(IMAGE_PREFIX)*" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.Created}}"

# =============================================================================
## Container Orchestration (Podman Compose)
# =============================================================================

.PHONY: up
up: ## Start all services with podman-compose
	@echo "$(BOLD)$(GREEN)▶ Starting all services...$(RESET)"
	@podman-compose -f $(COMPOSE_FILE) up -d
	@echo "$(GREEN)✓ All services running$(RESET)"
	@echo "$(CYAN)  Portal: http://localhost:$(PORTAL_PORT)$(RESET)"

.PHONY: down
down: ## Stop all services
	@echo "$(YELLOW)▶ Stopping all services...$(RESET)"
	@podman-compose -f $(COMPOSE_FILE) down
	@echo "$(GREEN)✓ All services stopped$(RESET)"

.PHONY: restart
restart: down up ## Restart all services

.PHONY: logs
logs: ## Show logs from all services (follow mode)
	@podman-compose -f $(COMPOSE_FILE) logs -f

.PHONY: logs-%
logs-%: ## Show logs for a specific service (e.g., make logs-portal)
	@podman-compose -f $(COMPOSE_FILE) logs -f $*

.PHONY: ps
ps: ## Show status of all running services
	@podman-compose -f $(COMPOSE_FILE) ps

# =============================================================================
## Kubernetes Deployment
# =============================================================================

.PHONY: k8s-cluster-create
k8s-cluster-create: ## Create a local k3d cluster
	@echo "$(BOLD)$(GREEN)▶ Creating k3d cluster '$(K3D_CLUSTER)'...$(RESET)"
	@k3d cluster create $(K3D_CLUSTER) \
		-p "$(PORTAL_PORT):80@loadbalancer" \
		--agents 2
	@echo "$(GREEN)✓ Cluster created$(RESET)"

.PHONY: k8s-cluster-delete
k8s-cluster-delete: ## Delete the local k3d cluster
	@echo "$(RED)▶ Deleting k3d cluster '$(K3D_CLUSTER)'...$(RESET)"
	@k3d cluster delete $(K3D_CLUSTER)
	@echo "$(GREEN)✓ Cluster deleted$(RESET)"

.PHONY: k8s-import
k8s-import: build ## Build images and import them into k3d
	@echo "$(BOLD)$(GREEN)▶ Importing images into k3d...$(RESET)"
	@for svc in $(SERVICES); do \
		echo "  Importing $(IMAGE_PREFIX)-$$svc:$(IMAGE_TAG)..."; \
		k3d image import $(IMAGE_PREFIX)-$$svc:$(IMAGE_TAG) -c $(K3D_CLUSTER); \
	done
	@echo "$(GREEN)✓ All images imported$(RESET)"

.PHONY: deploy-k8s
deploy-k8s: ## Deploy all manifests to Kubernetes
	@echo "$(BOLD)$(GREEN)▶ Deploying to Kubernetes...$(RESET)"
	@kubectl apply -f $(K8S_DIR)/namespace.yaml
	@kubectl apply -f $(K8S_DIR)/
	@echo "$(GREEN)✓ Deployed to Kubernetes$(RESET)"
	@echo "$(CYAN)  Waiting for pods...$(RESET)"
	@kubectl -n $(PROJECT_NAME) get pods

.PHONY: undeploy-k8s
undeploy-k8s: ## Remove all Kubernetes resources
	@echo "$(RED)▶ Removing Kubernetes resources...$(RESET)"
	@kubectl delete -f $(K8S_DIR)/ --ignore-not-found
	@echo "$(GREEN)✓ Resources removed$(RESET)"

.PHONY: k8s-status
k8s-status: ## Show Kubernetes pod and service status
	@echo "$(BOLD)$(CYAN)Pods:$(RESET)"
	@kubectl -n $(PROJECT_NAME) get pods -o wide
	@echo ""
	@echo "$(BOLD)$(CYAN)Services:$(RESET)"
	@kubectl -n $(PROJECT_NAME) get svc
	@echo ""
	@echo "$(BOLD)$(CYAN)Ingress:$(RESET)"
	@kubectl -n $(PROJECT_NAME) get ingress

.PHONY: k8s-logs
k8s-logs: ## Show logs from all pods (last 50 lines each)
	@for pod in $$(kubectl -n $(PROJECT_NAME) get pods -o name); do \
		echo "$(BOLD)$(CYAN)$$pod:$(RESET)"; \
		kubectl -n $(PROJECT_NAME) logs $$pod --tail=50; \
		echo ""; \
	done

# =============================================================================
## Full Pipeline
# =============================================================================

.PHONY: all
all: setup test build ## Full pipeline: setup + test + build containers

.PHONY: deploy-full
deploy-full: build k8s-cluster-create k8s-import deploy-k8s ## Full K8s pipeline: build → cluster → import → deploy

# =============================================================================
## Cleanup
# =============================================================================

.PHONY: clean
clean: clean-c ## Clean all build artifacts
	@echo "$(YELLOW)▶ Cleaning Python artifacts...$(RESET)"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ All artifacts cleaned$(RESET)"

.PHONY: clean-images
clean-images: ## Remove all project container images
	@echo "$(RED)▶ Removing project container images...$(RESET)"
	@podman rmi $$(podman images --filter "reference=$(IMAGE_PREFIX)*" -q) 2>/dev/null || true
	@echo "$(GREEN)✓ Images removed$(RESET)"

.PHONY: clean-all
clean-all: clean clean-images ## Clean everything (artifacts + images)
	@echo "$(GREEN)✓ Full cleanup complete$(RESET)"
