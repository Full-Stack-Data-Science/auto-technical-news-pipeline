output "identity_id" {
  value = azurerm_user_assigned_identity.this.id
}

output "identity_principal_id" {
  value = azurerm_user_assigned_identity.this.principal_id
}

output "job_id" {
  value = azurerm_container_app_job.this.id
}

output "job_name" {
  value = azurerm_container_app_job.this.name
}
