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
  type = string
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