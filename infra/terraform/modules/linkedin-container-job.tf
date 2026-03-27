variable "platform" {
  description = "Shared Azure runtime settings"
  type = object({
    location            = string
    resource_group_name = string
    env_id              = string
    acr_login_server    = string
    identity_name       = string
  })
}

variable "job" {
  description = "Container App Job schedule settings"
  type = object({
    name          = string
    cron_schedule = string
  })
}

variable "scraper" {
  description = "Scraper container image and runtime settings"
  type = object({
    image_name       = string
    image_tag        = string
    command          = optional(list(string), [])
    email            = string
    password         = string
    cookie_file      = optional(string, "/src/data/cookies/linkedin_cookies.json")
    linkedin_cookies = optional(string, "/src/data/cookies/linkedin_cookies.json")
    selenium_host    = optional(string, "selenium")
    selenium_port    = optional(string, "4444")
    python_path      = optional(string, "/src")
  })
  sensitive = true
}

variable "storage" {
  description = "Storage account settings used by the scraper"
  type = object({
    account_name     = string
    account_key      = string
    file_system_name = optional(string, "bronze")
  })
  sensitive = true
}

resource "azurerm_user_assigned_identity" "uami" {
  name                = var.platform.identity_name
  location            = var.platform.location
  resource_group_name = var.platform.resource_group_name
}

resource "azurerm_container_app_job" "linkedinScrapingJob" {
  name                         = var.job.name
  location                     = var.platform.location
  resource_group_name          = var.platform.resource_group_name
  container_app_environment_id = var.platform.env_id

  trigger_type               = "Schedule"
  replica_timeout_in_seconds = 3600

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.uami.id]
  }

  registry {
    server   = var.platform.acr_login_server
    identity = azurerm_user_assigned_identity.uami.id
  }

  schedule_trigger_config {
    cron_expression          = var.job.cron_schedule
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name   = "selenium"
      image  = "selenium/standalone-chrome:latest"
      cpu    = 1
      memory = "2Gi"

      env {
        name  = "SE_VNC_NO_PASSWORD"
        value = "1"
      }
    }

    container {
      name    = "scraper"
      image   = "${var.platform.acr_login_server}/${var.scraper.image_name}:${var.scraper.image_tag}"
      command = length(var.scraper.command) == 0 ? null : var.scraper.command
      cpu     = 1
      memory  = "2Gi"

      env {
        name  = "EMAIL"
        value = var.scraper.email
      }

      env {
        name  = "PASSWORD"
        value = var.scraper.password
      }

      env {
        name  = "COOKIE_FILE"
        value = var.scraper.cookie_file
      }

      env {
        name  = "LINKEDIN_COOKIES"
        value = var.scraper.linkedin_cookies
      }

      env {
        name  = "STORAGE_ACCOUNT_NAME"
        value = var.storage.account_name
      }

      env {
        name  = "STORAGE_ACCOUNT_KEY"
        value = var.storage.account_key
      }

      env {
        name  = "FILE_SYSTEM_NAME"
        value = var.storage.file_system_name
      }

      env {
        name  = "SELENIUM_HOST"
        value = var.scraper.selenium_host
      }

      env {
        name  = "SELENIUM_PORT"
        value = var.scraper.selenium_port
      }

      env {
        name  = "PYTHONPATH"
        value = var.scraper.python_path
      }
    }
  }
}

output "uamiId" {
  value = azurerm_user_assigned_identity.uami.id
}

output "jobId" {
  value = azurerm_container_app_job.linkedinScrapingJob.id
}