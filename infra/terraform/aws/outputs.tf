output "app_url" {
  value = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "alb_dns" {
  value = aws_lb.main.dns_name
}

output "ecr_backend" {
  value = aws_ecr_repository.repo["backend"].repository_url
}

output "ecr_frontend" {
  value = aws_ecr_repository.repo["frontend"].repository_url
}

output "cluster" {
  value = aws_ecs_cluster.main.name
}

output "api_service" {
  value = aws_ecs_service.api.name
}

output "web_service" {
  value = aws_ecs_service.web.name
}

output "subnets" {
  value = join(",", aws_subnet.public[*].id)
}

output "tasks_security_group" {
  value = aws_security_group.tasks.id
}

output "db_instance" {
  value = aws_db_instance.main.identifier
}

output "app_secret_id" {
  value = aws_secretsmanager_secret.app.name
}

output "github_deploy_role_arn" {
  value = aws_iam_role.github_deploy.arn
}
