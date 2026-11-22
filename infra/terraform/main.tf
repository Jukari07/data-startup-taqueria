# ==============================================================================
# main.tf — Infraestructura en AWS para Tacos Las Cazuelitas
# Aprovisiona S3 (raw y clean), colas SQS (principal + DLQ) y roles IAM con
# principio de mínimo privilegio.
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = var.common_tags
  }
}

# ------------------------------------------------------------------------------
# 1. ALMACENAMIENTO S3 (Data Lake: Zonas Raw y Clean)
# ------------------------------------------------------------------------------

# Bucket para datos crudos (append-only)
resource "aws_s3_bucket" "raw_bucket" {
  bucket        = "${var.project_name}-raw-${var.environment}"
  force_destroy = true # Facilita destrucción en ambientes de prueba académicos
}

resource "aws_s3_bucket_versioning" "raw_versioning" {
  bucket = aws_s3_bucket.raw_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_encryption" {
  bucket = aws_s3_bucket.raw_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Bucket para datos limpios y procesados
resource "aws_s3_bucket" "clean_bucket" {
  bucket        = "${var.project_name}-clean-${var.environment}"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "clean_versioning" {
  bucket = aws_s3_bucket.clean_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "clean_encryption" {
  bucket = aws_s3_bucket.clean_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ------------------------------------------------------------------------------
# 2. COLAS SQS (Mensajería con Cola de Mensajes Muertos - DLQ)
# ------------------------------------------------------------------------------

# Dead-Letter Queue (DLQ) para retener mensajes fallidos tras 3 reintentos
resource "aws_sqs_queue" "pedidos_dlq" {
  name                      = "${var.project_name}-pedidos-dlq"
  message_retention_seconds = 1209600 # 14 días
}

# Cola principal de pedidos con política de redrive
resource "aws_sqs_queue" "pedidos_queue" {
  name                       = "${var.project_name}-pedidos"
  visibility_timeout_seconds = 60
  receive_wait_time_seconds  = 20 # Long polling activado

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.pedidos_dlq.arn
    maxReceiveCount     = 3
  })
}

# ------------------------------------------------------------------------------
# 3. SEGURIDAD IAM (Rol y Políticas de Mínimo Privilegio para el Worker)
# ------------------------------------------------------------------------------

# Rol asumible por servicios de computo (Lambda y ECS Tasks)
resource "aws_iam_role" "worker_role" {
  name = "${var.project_name}-worker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "ecs-tasks.amazonaws.com"
          ]
        }
      }
    ]
  })
}

# Política de mínimo privilegio:
# - Solo lectura en taqueria-raw
# - Solo escritura en taqueria-clean
# - Consumo y eliminación en SQS principal
resource "aws_iam_policy" "worker_policy" {
  name        = "${var.project_name}-worker-policy"
  description = "Politica de minimo privilegio para procesar pedidos de raw a clean"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LeerRawS3"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.raw_bucket.arn,
          "${aws_s3_bucket.raw_bucket.arn}/*"
        ]
      },
      {
        Sid    = "EscribirCleanS3"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:AbortMultipartUpload"
        ]
        Resource = [
          "${aws_s3_bucket.clean_bucket.arn}/*"
        ]
      },
      {
        Sid    = "ConsumirSQS"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.pedidos_queue.arn
      },
      {
        Sid    = "LogsCloudWatch"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_worker_policy" {
  role       = aws_iam_role.worker_role.name
  policy_arn = aws_iam_policy.worker_policy.arn
}
