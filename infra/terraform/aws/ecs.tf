resource "aws_ecs_cluster" "main" {
  name = local.name
}

resource "aws_cloudwatch_log_group" "app" {
  for_each          = toset(["api", "gotenberg", "web"])
  name              = "/ecs/${local.name}/${each.key}"
  retention_in_days = 7
}

locals {
  api_image  = "${aws_ecr_repository.repo["backend"].repository_url}:${var.image_tag}"
  web_image  = "${aws_ecr_repository.repo["frontend"].repository_url}:${var.image_tag}"
  app_secret = aws_secretsmanager_secret.app.arn
  db_secret  = aws_db_instance.main.master_user_secret[0].secret_arn

  logs = { for k, g in aws_cloudwatch_log_group.app : k => {
    logDriver = "awslogs"
    options   = { "awslogs-group" = g.name, "awslogs-region" = var.region, "awslogs-stream-prefix" = k }
  } }
}

# api task: FastAPI + Gotenberg sidecar (reached on localhost:3000). Single replica: in-process
# TaskRunner and event bus (plan.md §11.1); scale-out = Redis + arq worker.
resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 3072
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name         = "api"
      image        = local.api_image
      essential    = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "APP_ENV", value = "aws" },
        { name = "LLM_MODE", value = "auto" },
        { name = "WEB_SEARCH_PROVIDER", value = "auto" },
        { name = "GOTENBERG_URL", value = "http://localhost:3000" },
        { name = "DB_HOST", value = aws_db_instance.main.address },
        { name = "DB_NAME", value = "policy" },
        { name = "LANGFUSE_HOST", value = var.langfuse_host },
        { name = "CORS_ORIGINS", value = "https://${aws_cloudfront_distribution.main.domain_name}" },
      ]
      secrets = [
        { name = "DB_USER", valueFrom = "${local.db_secret}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${local.db_secret}:password::" },
        { name = "OPENAI_API_KEY", valueFrom = "${local.app_secret}:OPENAI_API_KEY::" },
        { name = "GOOGLE_API_KEY", valueFrom = "${local.app_secret}:GOOGLE_API_KEY::" },
        { name = "LANGFUSE_PUBLIC_KEY", valueFrom = "${local.app_secret}:LANGFUSE_PUBLIC_KEY::" },
        { name = "LANGFUSE_SECRET_KEY", valueFrom = "${local.app_secret}:LANGFUSE_SECRET_KEY::" },
        { name = "TAVILY_API_KEY", valueFrom = "${local.app_secret}:TAVILY_API_KEY::" },
        { name = "APP_ACCESS_TOKEN", valueFrom = "${local.app_secret}:APP_ACCESS_TOKEN::" },
      ]
      logConfiguration = local.logs["api"]
      dependsOn        = [{ containerName = "gotenberg", condition = "START" }]
    },
    {
      name             = "gotenberg"
      image            = "gotenberg/gotenberg:8"
      essential        = false
      logConfiguration = local.logs["gotenberg"]
    }
  ])
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn

  container_definitions = jsonencode([{
    name         = "web"
    image        = local.web_image
    essential    = true
    portMappings = [{ containerPort = 8080, protocol = "tcp" }]
    # The ALB routes /api and /ws straight to the api service; nginx's proxy block only needs a
    # resolvable placeholder upstream so it can start.
    environment      = [{ name = "API_UPSTREAM", value = "http://127.0.0.1:8000" }]
    logConfiguration = local.logs["web"]
  }])
}

resource "aws_ecs_service" "api" {
  name                               = "${local.name}-api"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = 1
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 90
  deployment_minimum_healthy_percent = 0 # single replica: stop old before starting new
  deployment_maximum_percent         = 100

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  lifecycle {
    ignore_changes = [task_definition, desired_count] # owned by the deploy pipeline / make aws-pause
  }
  depends_on = [aws_lb_listener_rule.api]
}

resource "aws_ecs_service" "web" {
  name            = "${local.name}-web"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 8080
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
  depends_on = [aws_lb_listener.http]
}
