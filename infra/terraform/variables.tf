# ==============================================================================
# variables.tf — Variables de entrada para la infraestructura de Las Cazuelitas
# ==============================================================================

variable "aws_region" {
  description = "Región de AWS donde se aprovisionarán los recursos."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nombre base del proyecto para prefijar recursos."
  type        = string
  default     = "taqueria"
}

variable "environment" {
  description = "Ambiente de despliegue (dev, staging, prod)."
  type        = string
  default     = "prod"
}

variable "common_tags" {
  description = "Etiquetas comunes aplicadas a todos los recursos."
  type        = map(string)
  default = {
    Proyecto   = "Tacos Las Cazuelitas"
    Materia    = "Computo en la Nube / Analitica de Datos"
    Institucion = "TecNM Campus Colima"
    GestionadoPor = "Terraform"
  }
}
