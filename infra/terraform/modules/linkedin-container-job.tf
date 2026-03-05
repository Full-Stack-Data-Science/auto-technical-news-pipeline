variable "location" {
  type = string
}

variable "resourceGroupName" {
  description = "Resource group containing the Container App Job and identity"
  type        = string
}

variable "jobName" {
  type = string
}

variable "envId" {
  type = string
}

variable "acrLoginServer" {
  type = string
}

variable "scraperImage" {
  type = string
}

variable "scraperImageTag" {
  type = string
}

variable "scraperCommand" {
  description = "Optional command override for scraper container. Empty list uses image CMD."
  type        = list(string)
  default     = []
}

variable "identityName" {
  type = string
}

variable "cronSchedule" {
  type = string
}

variable "email" {
  type = string
}

variable "password" {
  type      = string
  sensitive = true
}

variable "cookieFile" {
  type    = string
  default = "/src/data/cookies/linkedin_cookies.json"
}

variable "linkedinCookies" {
  type    = string
  default = "/src/data/cookies/linkedin_cookies.json"
}

variable "storageAccountName" {
  type = string
}

variable "storageAccountKey" {
  type      = string
  sensitive = true
}

variable "fileSystemName" {
  type    = string
  default = "bronze"
}

variable "seleniumHost" {
  type    = string
  default = "selenium"
}

variable "seleniumPort" {
  type    = string
  default = "4444"
}

variable "pythonPath" {
  type    = string
  default = "/src"
}

resource "azurerm_user_assigned_identity" "uami" {
  name                = var.identityName
  location            = var.location
  resource_group_name = var.resourceGroupName
}

resource "azurerm_container_app_job" "linkedinScrapingJob" {
  name                         = var.jobName
  location                     = var.location
  resource_group_name          = var.resourceGroupName
  container_app_environment_id = var.envId

  trigger_type               = "Schedule"
  replica_timeout_in_seconds = 3600

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.uami.id]
  }

  registry {
    server   = var.acrLoginServer
    identity = azurerm_user_assigned_identity.uami.id
  }

  schedule_trigger_config {
    cron_expression          = var.cronSchedule
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
      image   = "${var.acrLoginServer}/${var.scraperImage}:${var.scraperImageTag}"
      command = length(var.scraperCommand) == 0 ? null : var.scraperCommand
      cpu     = 1
      memory  = "2Gi"

      env {
        name  = "EMAIL"
        value = var.email
      }

      env {
        name  = "PASSWORD"
        value = var.password
      }

      env {
        name  = "COOKIE_FILE"
        value = var.cookieFile
      }

      env {
        name  = "LINKEDIN_COOKIES"
        value = var.linkedinCookies
      }

      env {
        name  = "STORAGE_ACCOUNT_NAME"
        value = var.storageAccountName
      }

      env {
        name  = "STORAGE_ACCOUNT_KEY"
        value = var.storageAccountKey
      }

      env {
        name  = "FILE_SYSTEM_NAME"
        value = var.fileSystemName
      }

      env {
        name  = "SELENIUM_HOST"
        value = var.seleniumHost
      }

      env {
        name  = "SELENIUM_PORT"
        value = var.seleniumPort
      }

      env {
        name  = "PYTHONPATH"
        value = var.pythonPath
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
