terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

locals {
  names = {
    servicebus_namespace    = var.servicebus_namespace_name
    servicebus_topic        = var.servicebus_topic_name
    servicebus_subscription = var.servicebus_subscription_name

    container_app_env = var.container_app_environment_name
    container_app_job = var.container_app_job_name
  }

  job_env = {
    technical_channel_id = var.technical_channel_id
  }
}


# data
data "azurerm_resource_group" "rg" {
  name = var.resource_group_name
}
data "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = data.azurerm_resource_group.rg.name
}
data "azurerm_user_assigned_identity" "uami" {
  name                = var.uami_name
  resource_group_name = data.azurerm_resource_group.rg.name
}
data "azurerm_log_analytics_workspace" "law" {
  name                = var.log_analytics_name
  resource_group_name = data.azurerm_resource_group.rg.name
}
data "azurerm_servicebus_namespace" "sb" {
  name                = local.names.servicebus_namespace
  resource_group_name = data.azurerm_resource_group.rg.name
}
data "azurerm_servicebus_topic" "topic" {
  name         = local.names.servicebus_topic
  namespace_id = data.azurerm_servicebus_namespace.sb.id
}
data "azurerm_servicebus_subscription" "sub" {
  name     = local.names.servicebus_subscription
  topic_id = data.azurerm_servicebus_topic.topic.id
}


# azure container app jobs
resource "azurerm_role_assignment" "sb_receiver" {
  scope                = data.azurerm_servicebus_namespace.sb.id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = data.azurerm_user_assigned_identity.uami.principal_id
}

resource "azurerm_container_app_environment" "env" {
  name                = local.names.container_app_env
  location            = data.azurerm_resource_group.rg.location
  resource_group_name = data.azurerm_resource_group.rg.name

  log_analytics_workspace_id = data.azurerm_log_analytics_workspace.law.id
}
resource "azurerm_container_app_job" "job" {
  name                         = local.names.container_app_job
  location                     = data.azurerm_resource_group.rg.location
  resource_group_name          = data.azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id

  replica_timeout_in_seconds = 1800
  replica_retry_limit        = 3


  identity {
    type         = "UserAssigned"
    identity_ids = [data.azurerm_user_assigned_identity.uami.id]
  }

  registry {
    server   = data.azurerm_container_registry.acr.login_server
    identity = data.azurerm_user_assigned_identity.uami.id
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
    name  = "fsds-username"
    value = var.fsds_username
  }
  secret {
    name  = "fsds-password"
    value = var.fsds_password
  }

  template {
    container {
      name   = "job"
      image  = "${data.azurerm_container_registry.acr.login_server}/${var.container_image}"
      cpu    = 2
      memory = "4Gi"

      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }
      env {
        name  = "TECHNICAL_CHANNEL_ID"
        value = local.job_env.technical_channel_id
      }
      env {
        name        = "FSDS_USERNAME"
        secret_name = "fsds-username"
      }
      env {
        name        = "FSDS_PASSWORD"
        secret_name = "fsds-password"
      }
      env {
        name        = "SERVICE_BUS_CONNECTION_STRING"
        secret_name = "servicebus-connection"
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
