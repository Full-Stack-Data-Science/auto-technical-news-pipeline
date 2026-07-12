locals {
  sku_parts = split("_", var.sku)
}

resource "azurerm_storage_account" "this" {
  name                     = var.name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_kind             = "StorageV2"
  account_tier             = local.sku_parts[0]
  account_replication_type = local.sku_parts[1]

  # ADLS Gen2 hierarchical namespace
  is_hns_enabled = true

  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  https_traffic_only_enabled      = true
  access_tier                     = "Hot"

  tags = merge(var.tags, {
    Purpose = "DataLake"
    Type    = "ADLS-Gen2"
  })
}

resource "azurerm_storage_container" "bronze" {
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}
