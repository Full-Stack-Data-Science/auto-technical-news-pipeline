variable "name" {
  description = "Container App Job name"
  type        = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "container_app_environment_id" {
  type = string
}

variable "acr_login_server" {
  type = string
}

variable "identity_name" {
  description = "User-assigned managed identity name created for this job"
  type        = string
}

variable "image_name" {
  description = "Scraper image name (without registry prefix or tag)"
  type        = string
}

variable "image_tag" {
  description = "Scraper image tag"
  type        = string
  default     = "latest"
}

variable "cron_schedule" {
  description = "CRON expression for the job schedule (UTC)"
  type        = string
}

variable "replica_timeout_in_seconds" {
  description = "Maximum seconds a replica runs before being killed"
  type        = number
  default     = 3600
}

# Resource sizing — split so Twitter and LinkedIn can differ
variable "selenium_cpu" {
  type    = number
  default = 1
}

variable "selenium_memory" {
  type    = string
  default = "2Gi"
}

variable "scraper_cpu" {
  type    = number
  default = 1
}

variable "scraper_memory" {
  type    = string
  default = "2Gi"
}

variable "scraper_command" {
  description = "Override container entrypoint (leave empty to use image default)"
  type        = list(string)
  default     = []
}

variable "secrets" {
  description = "Secrets mounted into the job (name + value pairs)"
  type = list(object({
    name  = string
    value = string
  }))
  default   = []
  sensitive = true
}

variable "env_vars" {
  description = "Plain (non-sensitive) environment variables"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "secret_env_vars" {
  description = "Environment variables sourced from job secrets"
  type = list(object({
    name        = string
    secret_name = string
  }))
  default = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
