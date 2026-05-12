# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------
variable "resource_group_name" {
  description = "Existing Azure resource group"
  type        = string
}

variable "log_analytics_workspace_name" {
  description = "Existing Log Analytics Workspace used by the Container Apps Environment"
  type        = string
}

variable "tags" {
  description = "Extra tags merged onto all resources (Project/ManagedBy/Environment are added automatically)"
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# ACR
# ---------------------------------------------------------------------------
variable "acr_name" {
  description = "Azure Container Registry name (globally unique)"
  type        = string
}

variable "acr_sku" {
  description = "ACR pricing tier: Basic | Standard | Premium"
  type        = string
  default     = "Basic"
}

# ---------------------------------------------------------------------------
# Storage (ADLS Gen2)
# ---------------------------------------------------------------------------
variable "storage_account_name" {
  description = "Storage account name (globally unique, 3-24 lowercase alphanumeric)"
  type        = string
  default     = "technewsdlake001"
}

variable "storage_sku" {
  description = "Storage SKU, e.g. Standard_LRS or Standard_GRS"
  type        = string
  default     = "Standard_LRS"
}

variable "storage_container_name" {
  description = "Bronze-layer container (filesystem) name"
  type        = string
  default     = "bronze"
}

# ---------------------------------------------------------------------------
# Container Apps Environment
# ---------------------------------------------------------------------------
variable "container_app_environment_name" {
  description = "Shared Container Apps Environment name"
  type        = string
  default     = "cae-scraper-jobs"
}

# ---------------------------------------------------------------------------
# Twitter scraper job
# ---------------------------------------------------------------------------
variable "twitter_job" {
  description = "Twitter scraper job settings"
  type = object({
    name          = string
    image_name    = string
    image_tag     = optional(string, "latest")
    cron_schedule = string
  })
  default = {
    name          = "twitter-scraper-job"
    image_name    = "twitter-scraper"
    image_tag     = "latest"
    cron_schedule = "0 */6 * * *"
  }
}

variable "twitter_credentials" {
  description = "Twitter login credentials (stored as Container App Job secrets)"
  type = object({
    email    = string
    password = string
  })
  sensitive = true
}

# ---------------------------------------------------------------------------
# LinkedIn scraper job
# ---------------------------------------------------------------------------
variable "linkedin_job" {
  description = "LinkedIn scraper job settings"
  type = object({
    name          = string
    image_name    = string
    image_tag     = optional(string, "latest")
    cron_schedule = string
    command       = optional(list(string), [])
  })
  default = {
    name          = "linkedin-scraper-job"
    image_name    = "linkedin-scraper"
    image_tag     = "latest"
    cron_schedule = "0 */8 * * *"
    command       = []
  }
}

variable "linkedin_credentials" {
  description = "LinkedIn login credentials (stored as Container App Job secrets)"
  type = object({
    email    = string
    password = string
  })
  sensitive = true
}

# ---------------------------------------------------------------------------
# Publisher job (event-triggered)
# ---------------------------------------------------------------------------
variable "publisher_job_name" {
  description = "Publisher Container App Job name"
  type        = string
  default     = "post-publisher-job"
}

variable "publisher_container_image" {
  description = "Publisher image name:tag (without registry prefix)"
  type        = string
  default     = "post-publisher:latest"
}

variable "servicebus_namespace_name" {
  description = "Existing Service Bus namespace name"
  type        = string
  default     = "post-events-ns"
}

variable "servicebus_topic_name" {
  description = "Service Bus topic that triggers the publisher"
  type        = string
  default     = "new-post-events"
}

variable "servicebus_subscription_name" {
  description = "Service Bus subscription the publisher consumes"
  type        = string
  default     = "logger"
}

variable "discord_webhook_url" {
  description = "Discord webhook URL for publishing post summaries"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key (optional — leave empty if using Anthropic only)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "anthropic_api_key" {
  description = "Anthropic API key (optional — leave empty if using OpenAI only)"
  type        = string
  sensitive   = true
  default     = ""
}

