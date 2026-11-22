# ==============================================================================
# outputs.tf — Salidas exportadas por Terraform para configuración de la app
# ==============================================================================

output "raw_bucket_name" {
  description = "Nombre del bucket S3 para datos crudos (raw)"
  value       = aws_s3_bucket.raw_bucket.id
}

output "clean_bucket_name" {
  description = "Nombre del bucket S3 para datos limpios (clean)"
  value       = aws_s3_bucket.clean_bucket.id
}

output "queue_url" {
  description = "URL de la cola SQS principal de pedidos"
  value       = aws_sqs_queue.pedidos_queue.id
}

output "queue_arn" {
  description = "ARN de la cola SQS principal de pedidos"
  value       = aws_sqs_queue.pedidos_queue.arn
}

output "dlq_url" {
  description = "URL de la Dead Letter Queue (DLQ)"
  value       = aws_sqs_queue.pedidos_dlq.id
}

output "worker_role_arn" {
  description = "ARN del rol IAM asignado al worker"
  value       = aws_iam_role.worker_role.arn
}
