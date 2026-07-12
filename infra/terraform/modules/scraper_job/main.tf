resource "azurerm_user_assigned_identity" "this" {
  name                = var.identity_name
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_container_app_job" "this" {
  name                         = var.name
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.container_app_environment_id

  trigger_type               = "Schedule"
  replica_timeout_in_seconds = var.replica_timeout_in_seconds

  tags = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  registry {
    server   = var.acr_login_server
    identity = azurerm_user_assigned_identity.this.id
  }

  dynamic "secret" {
    for_each = var.secrets
    content {
      name  = secret.value.name
      value = secret.value.value
    }
  }

  schedule_trigger_config {
    cron_expression          = var.cron_schedule
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name   = "selenium"
      image  = "selenium/standalone-chrome:latest"
      cpu    = var.selenium_cpu
      memory = var.selenium_memory

      env {
        name  = "SE_VNC_NO_PASSWORD"
        value = "1"
      }
    }

    container {
      name    = "scraper"
      image   = "${var.acr_login_server}/${var.image_name}:${var.image_tag}"
      command = length(var.scraper_command) > 0 ? var.scraper_command : null
      cpu     = var.scraper_cpu
      memory  = var.scraper_memory

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name        = env.value.name
          secret_name = env.value.secret_name
        }
      }
    }
  }
}
