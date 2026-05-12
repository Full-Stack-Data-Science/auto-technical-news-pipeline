locals {
  tags = merge(
    {
      Project     = "auto-technical-news-pipeline"
      ManagedBy   = "Terraform"
      Environment = terraform.workspace
    },
    var.tags,
  )
}
