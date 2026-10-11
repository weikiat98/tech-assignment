#!/usr/bin/env bash
# Build -> push to ECR -> run migrations (one-off task) -> roll both ECS services -> wait -> smoke test.
# Used by `make aws-deploy` (your machine) and .github/workflows/deploy-ecs.yml (CI via OIDC).
# Reads settings from env, falling back to `terraform output` when run locally.
set -euo pipefail

REGION="${AWS_REGION:-ap-southeast-1}"
TF_DIR="$(dirname "$0")/../terraform/aws"
tf() { terraform -chdir="$TF_DIR" output -raw "$1"; }

# Without Terraform (e.g. in GitHub Actions) every setting must come from the environment: name the gaps.
if ! command -v terraform >/dev/null 2>&1; then
  missing=""
  for v in ECR_BACKEND ECR_FRONTEND CLUSTER API_SERVICE WEB_SERVICE SUBNETS TASKS_SG APP_URL; do
    [ -n "${!v:-}" ] || missing="$missing $v"
  done
  if [ -n "$missing" ]; then
    echo "::error::Empty settings:$missing. In GitHub: Settings > Secrets and variables > Actions > Variables tab (not Secrets); names must match exactly."
    exit 1
  fi
fi

ECR_BACKEND="${ECR_BACKEND:-$(tf ecr_backend)}"
ECR_FRONTEND="${ECR_FRONTEND:-$(tf ecr_frontend)}"
CLUSTER="${CLUSTER:-$(tf cluster)}"
API_SERVICE="${API_SERVICE:-$(tf api_service)}"
WEB_SERVICE="${WEB_SERVICE:-$(tf web_service)}"
SUBNETS="${SUBNETS:-$(tf subnets)}"
TASKS_SG="${TASKS_SG:-$(tf tasks_security_group)}"
APP_URL="${APP_URL:-$(tf app_url)}"
TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"

echo "==> Logging in to ECR"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${ECR_BACKEND%%/*}"

echo "==> Building and pushing images ($TAG)"
# Fargate runs x86_64; --platform keeps Apple Silicon Macs from building arm64 images.
docker build --platform linux/amd64 -t "$ECR_BACKEND:$TAG" backend
docker build --platform linux/amd64 -t "$ECR_FRONTEND:$TAG" frontend
docker push "$ECR_BACKEND:$TAG"
docker push "$ECR_FRONTEND:$TAG"

# New task-definition revision = current one with only the image swapped.
new_revision() {
  local service="$1" container="$2" image="$3"
  local current taskdef
  current=$(aws ecs describe-services --cluster "$CLUSTER" --services "$service" --region "$REGION" \
    --query 'services[0].taskDefinition' --output text)
  # Passed inline rather than via a temp file: under Git Bash on Windows, /tmp and the AWS CLI's file:// differ.
  taskdef=$(aws ecs describe-task-definition --task-definition "$current" --region "$REGION" --query taskDefinition \
    | jq -c --arg c "$container" --arg img "$image" \
      '.containerDefinitions |= map(if .name == $c then .image = $img else . end)
       | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')
  aws ecs register-task-definition --cli-input-json "$taskdef" --region "$REGION" \
    --query 'taskDefinition.taskDefinitionArn' --output text
}

API_TD=$(new_revision "$API_SERVICE" api "$ECR_BACKEND:$TAG")
WEB_TD=$(new_revision "$WEB_SERVICE" web "$ECR_FRONTEND:$TAG")
echo "    api: $API_TD"
echo "    web: $WEB_TD"

echo "==> Running migrations (one-off task)"
TASK_ARN=$(aws ecs run-task --cluster "$CLUSTER" --launch-type FARGATE --task-definition "$API_TD" --region "$REGION" \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${TASKS_SG}],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"api","command":["python","-m","app.db.init"]}]}' \
  --query 'tasks[0].taskArn' --output text)
aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN" --region "$REGION"
EXIT=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN" --region "$REGION" \
  --query "tasks[0].containers[?name=='api'].exitCode | [0]" --output text)
[ "$EXIT" = "0" ] || { echo "migration task failed (exit $EXIT)"; exit 1; }

echo "==> Rolling services"
aws ecs update-service --cluster "$CLUSTER" --service "$API_SERVICE" --task-definition "$API_TD" --region "$REGION" >/dev/null
aws ecs update-service --cluster "$CLUSTER" --service "$WEB_SERVICE" --task-definition "$WEB_TD" --region "$REGION" >/dev/null
aws ecs wait services-stable --cluster "$CLUSTER" --services "$API_SERVICE" "$WEB_SERVICE" --region "$REGION"

echo "==> Smoke test $APP_URL/readyz"
curl -sf "$APP_URL/readyz" && echo && echo "Deployed $TAG -> $APP_URL"
