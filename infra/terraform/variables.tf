variable "resource_group_name" {
  type = string
}
variable "acr_name" {
  type = string
}
variable "uami_name" {
  type = string
}
variable "log_analytics_name" {
  type        = string
  description = "Log Analytics Workspace name"
}
variable "container_image" {
  type        = string
  description = "Container image name + tag (without ACR login server), e.g. post-publisher:latest"
  default     = "post-publisher:latest"
}

# credentials for container app jobs
variable "openai_api_key" {
  type      = string
  sensitive = true
}
variable "fsds_username" {
  type      = string
  sensitive = true
}
variable "fsds_password" {
  type      = string
  sensitive = true
}

variable "servicebus_namespace_name" {
  type        = string
  description = "Azure Service Bus namespace name"
  default     = "post-events-ns"
}

variable "servicebus_topic_name" {
  type        = string
  description = "Azure Service Bus topic name"
  default     = "new-post-events"
}

variable "servicebus_subscription_name" {
  type        = string
  description = "Azure Service Bus subscription name"
  default     = "logger"
}

variable "container_app_environment_name" {
  type        = string
  description = "Container Apps Environment name"
  default     = "cae-jobs"
}

variable "container_app_job_name" {
  type        = string
  description = "Container App Job name"
  default     = "example-job"
}

variable "technical_channel_id" {
  type        = string
  description = "TECHNICAL_CHANNEL_ID env var passed to the job"
}