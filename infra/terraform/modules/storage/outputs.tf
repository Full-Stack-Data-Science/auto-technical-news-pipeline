output "id" {
  value = azurerm_storage_account.this.id
}

output "name" {
  value = azurerm_storage_account.this.name
}

output "dfs_endpoint" {
  value = azurerm_storage_account.this.primary_dfs_endpoint
}

output "primary_access_key" {
  value     = azurerm_storage_account.this.primary_access_key
  sensitive = true
}

output "connection_string" {
  value     = azurerm_storage_account.this.primary_connection_string
  sensitive = true
}
