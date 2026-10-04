# --- container registry ----------------------------------------------------------------

resource "aws_ecr_repository" "repo" {
  for_each             = toset(["backend", "frontend"])
  name                 = "${local.name}-${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "keep_10" {
  for_each   = aws_ecr_repository.repo
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the last 10 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}

# --- database ---------------------------------------------------------------------------

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  identifier                  = local.name
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = "db.t4g.micro"
  allocated_storage           = 20
  storage_type                = "gp3"
  db_name                     = "policy"
  username                    = "policy"
  manage_master_user_password = true # password generated and kept in Secrets Manager, never in state
  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [aws_security_group.db.id]
  publicly_accessible         = false
  multi_az                    = false
  backup_retention_period     = 1
  skip_final_snapshot         = true
  deletion_protection         = false
  apply_immediately           = true
}

# --- application secrets ------------------------------------------------------------------
# Terraform creates the container with placeholders only; real values are set out-of-band:
#   aws secretsmanager put-secret-value --secret-id policy-analytics/app --secret-string file://secrets.json

resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.name}/app"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "app_placeholder" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    OPENAI_API_KEY      = "sk-REPLACE_ME"
    GOOGLE_API_KEY      = "REPLACE_ME"
    LANGFUSE_PUBLIC_KEY = "pk-lf-REPLACE_ME"
    LANGFUSE_SECRET_KEY = "sk-lf-REPLACE_ME"
    TAVILY_API_KEY      = "tvly-REPLACE_ME"
    APP_ACCESS_TOKEN    = "REPLACE_ME"
  })
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# --- cost guard ---------------------------------------------------------------------------

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alert_email]
    }
  }
}
