variable "name" {
  description = "Storage account name (globally unique, 3-24 lowercase alphanumeric)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sku" {
  description = "Storage SKU, e.g. Standard_LRS or Standard_GRS"
  type        = string
  default     = "Standard_LRS"
}

variable "container_name" {
  description = "Bronze-layer container (filesystem) name"
  type        = string
  default     = "bronze"
}

variable "tags" {
  type    = map(string)
  default = {}
}
