# Remote state keeps terraform.tfstate out of source control and enables
# team collaboration. Uncomment and fill in your own values to enable.
#
# terraform {
#   backend "azurerm" {
#     resource_group_name  = "rg-terraform-state"
#     storage_account_name = "tfstate<unique-suffix>"   # e.g. tfstate7f3a
#     container_name       = "tfstate"
#     key                  = "auto-technical-news-pipeline.tfstate"
#   }
# }
#
# Bootstrap the state storage account once with:
#   az group create -n rg-terraform-state -l southeastasia
#   az storage account create -n tfstate<suffix> -g rg-terraform-state --sku Standard_LRS
#   az storage container create -n tfstate --account-name tfstate<suffix>
