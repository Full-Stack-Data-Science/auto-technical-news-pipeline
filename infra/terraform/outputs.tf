output "acr_login_server" {
  description = "ACR login server — use this as the registry prefix when pushing images"
  value       = module.acr.login_server
}

output "storage_account_name" {
  description = "ADLS Gen2 storage account name"
  value       = module.storage.name
}

output "storage_dfs_endpoint" {
  description = "ADLS Gen2 DFS endpoint"
  value       = module.storage.dfs_endpoint
}

output "container_app_environment_id" {
  description = "Shared Container Apps Environment resource ID"
  value       = azurerm_container_app_environment.env.id
}

output "twitter_scraper_job_name" {
  value = module.twitter_scraper.job_name
}

output "linkedin_scraper_job_name" {
  value = module.linkedin_scraper.job_name
}

output "publisher_job_name" {
  value = azurerm_container_app_job.publisher.name
}
