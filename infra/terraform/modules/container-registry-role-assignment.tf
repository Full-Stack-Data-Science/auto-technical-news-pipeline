variable "registryName" {
  type = string
}

variable "registryResourceGroupName" {
  description = "Resource group name containing the Container Registry"
  type        = string
}

variable "roleId" {
  description = "Role definition GUID"
  type        = string
}

variable "principalId" {
  type = string
}

data "azurerm_client_config" "current" {}

data "azurerm_container_registry" "registry" {
  name                = var.registryName
  resource_group_name = var.registryResourceGroupName
}

resource "azurerm_role_assignment" "registry_role_assignment" {
  scope                            = data.azurerm_container_registry.registry.id
  role_definition_id               = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${var.roleId}"
  principal_id                     = var.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

output "roleAssignmentId" {
  value = azurerm_role_assignment.registry_role_assignment.id
}
