variable "storageAccountName" {
  description = "Storage Account name"
  type        = string
  default     = "technewsdlake001"
}

variable "resourceGroupName" {
  description = "Resource group name for storage account"
  type        = string
}

variable "location" {
  description = "Location"
  type        = string
  default     = "southeastasia"
}

variable "storageSku" {
  description = "Storage SKU"
  type        = string
  default     = "Standard_LRS"
}

variable "bronzeFileSystemName" {
  description = "Bronze filesystem name"
  type        = string
  default     = "bronze"
}

resource "azurerm_storage_account" "storageAccount" {
  name                     = var.storageAccountName
  resource_group_name      = var.resourceGroupName
  location                 = var.location
  account_kind             = "StorageV2"
  account_tier             = split("_", var.storageSku)[0]
  account_replication_type = split("_", var.storageSku)[1]

  is_hns_enabled                  = true
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  https_traffic_only_enabled      = true
  access_tier                     = "Hot"

  tags = {
    Purpose = "DataLake"
    Type    = "ADLS-Gen2"
  }
}

resource "azurerm_storage_container" "bronzeFileSystem" {
  name                  = var.bronzeFileSystemName
  storage_account_id    = azurerm_storage_account.storageAccount.id
  container_access_type = "private"
}

output "storageAccountId" {
  value = azurerm_storage_account.storageAccount.id
}

output "storageAccountName" {
  value = azurerm_storage_account.storageAccount.name
}

output "dfsEndpoint" {
  value = azurerm_storage_account.storageAccount.primary_dfs_endpoint
}

output "storageAccountKey" {
  value     = azurerm_storage_account.storageAccount.primary_access_key
  sensitive = true
}

output "connectionString" {
  value     = azurerm_storage_account.storageAccount.primary_connection_string
  sensitive = true
}
