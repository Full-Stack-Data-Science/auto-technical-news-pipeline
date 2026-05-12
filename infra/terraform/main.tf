# ---------------------------------------------------------------------------
# Existing shared resources
# ---------------------------------------------------------------------------
data "azurerm_resource_group" "rg" {
  name = var.resource_group_name
}

data "azurerm_log_analytics_workspace" "law" {
  name                = var.log_analytics_workspace_name
  resource_group_name = data.azurerm_resource_group.rg.name
}

# ---------------------------------------------------------------------------
# Azure Container Registry
# ---------------------------------------------------------------------------
module "acr" {
  source = "./modules/acr"

  name                = var.acr_name
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = data.azurerm_resource_group.rg.location
  sku                 = var.acr_sku
  tags                = local.tags
}

# ---------------------------------------------------------------------------
# ADLS Gen2 Storage
# ---------------------------------------------------------------------------
module "storage" {
  source = "./modules/storage"

  name                = var.storage_account_name
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = data.azurerm_resource_group.rg.location
  sku                 = var.storage_sku
  container_name      = var.storage_container_name
  tags                = local.tags
}

# ---------------------------------------------------------------------------
# Shared Container Apps Environment
# ---------------------------------------------------------------------------
resource "azurerm_container_app_environment" "env" {
  name                       = var.container_app_environment_name
  location                   = data.azurerm_resource_group.rg.location
  resource_group_name        = data.azurerm_resource_group.rg.name
  log_analytics_workspace_id = data.azurerm_log_analytics_workspace.law.id
  tags                       = local.tags
}

# ---------------------------------------------------------------------------
# Twitter scraper job
# ---------------------------------------------------------------------------
module "twitter_scraper" {
  source = "./modules/scraper_job"

  name                         = var.twitter_job.name
  location                     = data.azurerm_resource_group.rg.location
  resource_group_name          = data.azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  acr_login_server             = module.acr.login_server
  identity_name                = "${var.twitter_job.name}-uami"
  image_name                   = var.twitter_job.image_name
  image_tag                    = var.twitter_job.image_tag
  cron_schedule                = var.twitter_job.cron_schedule
  replica_timeout_in_seconds   = 7200
  selenium_cpu                 = 1.5
  selenium_memory              = "2.4Gi"
  scraper_cpu                  = 0.5
  scraper_memory               = "1.6Gi"
  tags                         = local.tags

  secrets = [
    { name = "twitter-email",    value = var.twitter_credentials.email },
    { name = "twitter-password", value = var.twitter_credentials.password },
    { name = "storage-key",      value = module.storage.primary_access_key },
  ]

  secret_env_vars = [
    { name = "TWITTER_EMAIL",       secret_name = "twitter-email" },
    { name = "TWITTER_PASSWORD",    secret_name = "twitter-password" },
    { name = "STORAGE_ACCOUNT_KEY", secret_name = "storage-key" },
  ]

  env_vars = [
    { name = "STORAGE_ACCOUNT_NAME", value = module.storage.name },
    { name = "FILE_SYSTEM_NAME",     value = var.storage_container_name },
    { name = "SELENIUM_HOST",        value = "selenium" },
    { name = "PYTHONPATH",           value = "/src" },
  ]
}

# ---------------------------------------------------------------------------
# LinkedIn scraper job
# ---------------------------------------------------------------------------
module "linkedin_scraper" {
  source = "./modules/scraper_job"

  name                         = var.linkedin_job.name
  location                     = data.azurerm_resource_group.rg.location
  resource_group_name          = data.azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  acr_login_server             = module.acr.login_server
  identity_name                = "${var.linkedin_job.name}-uami"
  image_name                   = var.linkedin_job.image_name
  image_tag                    = var.linkedin_job.image_tag
  cron_schedule                = var.linkedin_job.cron_schedule
  scraper_command              = var.linkedin_job.command
  replica_timeout_in_seconds   = 3600
  tags                         = local.tags

  secrets = [
    { name = "linkedin-email",    value = var.linkedin_credentials.email },
    { name = "linkedin-password", value = var.linkedin_credentials.password },
    { name = "storage-key",       value = module.storage.primary_access_key },
  ]

  secret_env_vars = [
    { name = "LINKEDIN_EMAIL",      secret_name = "linkedin-email" },
    { name = "LINKEDIN_PASSWORD",   secret_name = "linkedin-password" },
    { name = "STORAGE_ACCOUNT_KEY", secret_name = "storage-key" },
  ]

  env_vars = [
    { name = "STORAGE_ACCOUNT_NAME", value = module.storage.name },
    { name = "FILE_SYSTEM_NAME",     value = var.storage_container_name },
    { name = "SELENIUM_HOST",        value = "selenium" },
    { name = "PYTHONPATH",           value = "/src" },
  ]
}

# ---------------------------------------------------------------------------
# ACR pull role for each scraper identity
# ---------------------------------------------------------------------------
resource "azurerm_role_assignment" "twitter_acr_pull" {
  scope                = module.acr.id
  role_definition_name = "AcrPull"
  principal_id         = module.twitter_scraper.identity_principal_id
}

resource "azurerm_role_assignment" "linkedin_acr_pull" {
  scope                = module.acr.id
  role_definition_name = "AcrPull"
  principal_id         = module.linkedin_scraper.identity_principal_id
}

# ---------------------------------------------------------------------------
# Publisher job — event-triggered via Service Bus
# ---------------------------------------------------------------------------
data "azurerm_servicebus_namespace" "sb" {
  name                = var.servicebus_namespace_name
  resource_group_name = data.azurerm_resource_group.rg.name
}

data "azurerm_servicebus_topic" "topic" {
  name         = var.servicebus_topic_name
  namespace_id = data.azurerm_servicebus_namespace.sb.id
}

data "azurerm_servicebus_subscription" "sub" {
  name     = var.servicebus_subscription_name
  topic_id = data.azurerm_servicebus_topic.topic.id
}

resource "azurerm_user_assigned_identity" "publisher" {
  name                = "${var.publisher_job_name}-uami"
  location            = data.azurerm_resource_group.rg.location
  resource_group_name = data.azurerm_resource_group.rg.name
  tags                = local.tags
}

resource "azurerm_role_assignment" "publisher_acr_pull" {
  scope                = module.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.publisher.principal_id
}

resource "azurerm_role_assignment" "publisher_sb_receiver" {
  scope                = data.azurerm_servicebus_namespace.sb.id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = azurerm_user_assigned_identity.publisher.principal_id
}

resource "azurerm_container_app_job" "publisher" {
  name                         = var.publisher_job_name
  location                     = data.azurerm_resource_group.rg.location
  resource_group_name          = data.azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id

  replica_timeout_in_seconds = 1800
  replica_retry_limit        = 3
  tags                       = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.publisher.id]
  }

  registry {
    server   = module.acr.login_server
    identity = azurerm_user_assigned_identity.publisher.id
  }

  secret {
    name  = "servicebus-connection"
    value = data.azurerm_servicebus_namespace.sb.default_primary_connection_string
  }
  secret {
    name  = "openai-api-key"
    value = var.openai_api_key
  }
  secret {
    name  = "anthropic-api-key"
    value = var.anthropic_api_key
  }
  secret {
    name  = "discord-webhook-url"
    value = var.discord_webhook_url
  }

  template {
    container {
      name   = "publisher"
      image  = "${module.acr.login_server}/${var.publisher_container_image}"
      cpu    = 2
      memory = "4Gi"

      env {
        name        = "SERVICE_BUS_CONNECTION_STRING"
        secret_name = "servicebus-connection"
      }
      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }
      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-api-key"
      }
      env {
        name        = "DISCORD_WEBHOOK_URL"
        secret_name = "discord-webhook-url"
      }
      env {
        name  = "PYTHONPATH"
        value = "/src"
      }
    }
  }

  event_trigger_config {
    replica_completion_count = 1
    parallelism              = 1

    scale {
      min_executions = 0
      max_executions = 20

      rules {
        name             = "servicebus-topic"
        custom_rule_type = "azure-servicebus"

        metadata = {
          namespace        = data.azurerm_servicebus_namespace.sb.name
          topicName        = data.azurerm_servicebus_topic.topic.name
          subscriptionName = data.azurerm_servicebus_subscription.sub.name
          messageCount     = "1"
        }

        authentication {
          trigger_parameter = "connection"
          secret_name       = "servicebus-connection"
        }
      }
    }
  }
}
