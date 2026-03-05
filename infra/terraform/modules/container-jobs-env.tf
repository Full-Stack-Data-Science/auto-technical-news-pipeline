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
  default = "/src/data/cookies/twitter_cookies.json"
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

resource "azurerm_user_assigned_identity" "uami" {
  name                = var.identityName
  location            = var.location
  resource_group_name = var.resourceGroupName
}

resource "azurerm_container_app_job" "twitterScarpingJob" {
  name                         = var.jobName
  location                     = var.location
  resource_group_name          = var.resourceGroupName
  container_app_environment_id = var.envId

  trigger_type               = "Schedule"
  replica_timeout_in_seconds = 7200

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
      cpu    = 1.5
      memory = "2.4Gi"
    }

    container {
      name   = "scraper"
      image  = "${var.acrLoginServer}/${var.scraperImage}:${var.scraperImageTag}"
      cpu    = 0.5
      memory = "1.6Gi"

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
    }
  }
}

output "uamiId" {
  value = azurerm_user_assigned_identity.uami.id
}

output "jobId" {
  value = azurerm_container_app_job.twitterScarpingJob.id
}
