variable "acrName" {
  description = "Name of the Azure Container Registry (must be globally unique)"
  type        = string
}

variable "resourceGroupName" {
  description = "Resource group name where ACR is deployed"
  type        = string
}

variable "location" {
  description = "Location for the ACR"
  type        = string
  default     = null
}

variable "acrSku" {
  description = "Provide a tier of your Azure Container Registry."
  type        = string
  default     = "Basic"
}

data "azurerm_resource_group" "rg" {
  name = var.resourceGroupName
}

resource "azurerm_container_registry" "acr" {
  name                = var.acrName
  resource_group_name = var.resourceGroupName
  location            = var.location != null ? var.location : data.azurerm_resource_group.rg.location
  sku                 = var.acrSku
  admin_enabled       = false
}

output "acrName" {
  value = azurerm_container_registry.acr.name
}

output "acrId" {
  value = azurerm_container_registry.acr.id
}

output "loginServer" {
  value = azurerm_container_registry.acr.login_server
}
