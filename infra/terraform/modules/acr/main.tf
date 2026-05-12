data "azurerm_resource_group" "rg" {
  name = var.resource_group_name
}

resource "azurerm_container_registry" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = coalesce(var.location, data.azurerm_resource_group.rg.location)
  sku                 = var.sku
  admin_enabled       = false
  tags                = var.tags
}
