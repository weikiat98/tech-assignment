.PHONY: install up down logs dev-api dev-web test lint load load-stack samples cli aws-plan aws-apply aws-deploy aws-pause aws-resume aws-destroy

AWS_REGION ?= ap-southeast-1
TF_DIR := infra/terraform/aws
# Backend commands go through `uv run`, which syncs backend/.venv to uv.lock first (same on Windows/macOS/Linux)
UV := uv run --locked

# --- local ---------------------------------------------------------------------------
install:       ## backend venv from uv.lock (incl. dev tools) + frontend node_modules
	cd backend && uv sync --locked
	cd frontend && npm ci
up:            ## full stack via docker compose
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f api
dev-api:       ## backend with reload (SQLite)
	cd backend && $(UV) uvicorn app.main:app --reload --port 8000
dev-web:       ## frontend dev server (proxies to :8000)
	cd frontend && npm run dev
cli:           ## one analysis in the terminal: make cli Q="..."
	cd backend && $(UV) python -m app.cli "$(Q)"
samples:       ## rebuild MOM sample workbook + record source snapshots
	cd backend && $(UV) python -m app.scripts.build_samples

# --- quality -------------------------------------------------------------------------
test:
	cd backend && $(UV) pytest -m "not contract and not llm" --cov=app --cov-report=term --cov-report=html
lint:
	cd backend && $(UV) ruff check app tests
	cd frontend && npm run lint
load-stack:    ## restart the api offline + mock LLM + no tracing, for `make load`
	docker compose -f docker-compose.yml -f docker-compose.loadtest.yml up -d --build
load:          ## headless load test against a running stack
	cd backend && $(UV) locust -f tests/load/locustfile.py --host http://localhost:8000 --headless -u 50 -r 10 -t 2m --csv ../load-results

# --- AWS (ECS Fargate) - apply/destroy create or remove billable resources --------------
aws-plan:
	cd $(TF_DIR) && terraform init -upgrade && terraform plan -out tfplan
aws-apply:
	cd $(TF_DIR) && terraform apply tfplan
aws-deploy:    ## build, push to ECR, migrate, roll services (manual fallback to the CI pipeline)
	bash infra/scripts/deploy.sh
aws-pause:     ## scale to zero + stop RDS between sessions
	bash infra/scripts/pause.sh pause
aws-resume:
	bash infra/scripts/pause.sh resume
aws-destroy:
	cd $(TF_DIR) && terraform destroy
