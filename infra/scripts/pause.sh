#!/usr/bin/env bash
# pause: scale both services to 0 and stop RDS (costs drop to ~ALB + storage).
# resume: start RDS, wait until available, scale services back to 1.
# Note: AWS restarts a stopped RDS instance automatically after 7 days.
set -euo pipefail
REGION="${AWS_REGION:-ap-southeast-1}"
TF_DIR="$(dirname "$0")/../terraform/aws"
tf() { terraform -chdir="$TF_DIR" output -raw "$1"; }
CLUSTER=$(tf cluster); API=$(tf api_service); WEB=$(tf web_service); DB=$(tf db_instance)

case "${1:-}" in
  pause)
    aws ecs update-service --cluster "$CLUSTER" --service "$API" --desired-count 0 --region "$REGION" >/dev/null
    aws ecs update-service --cluster "$CLUSTER" --service "$WEB" --desired-count 0 --region "$REGION" >/dev/null
    aws rds stop-db-instance --db-instance-identifier "$DB" --region "$REGION" >/dev/null
    echo "paused (services at 0, RDS stopping)";;
  resume)
    aws rds start-db-instance --db-instance-identifier "$DB" --region "$REGION" >/dev/null || true
    aws rds wait db-instance-available --db-instance-identifier "$DB" --region "$REGION"
    aws ecs update-service --cluster "$CLUSTER" --service "$API" --desired-count 1 --region "$REGION" >/dev/null
    aws ecs update-service --cluster "$CLUSTER" --service "$WEB" --desired-count 1 --region "$REGION" >/dev/null
    aws ecs wait services-stable --cluster "$CLUSTER" --services "$API" "$WEB" --region "$REGION"
    echo "resumed: $(tf app_url)";;
  *) echo "usage: $0 pause|resume"; exit 2;;
esac
