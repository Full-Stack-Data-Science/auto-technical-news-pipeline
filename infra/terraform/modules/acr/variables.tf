variable "name" {
  description = "ACR name (globally unique, 5-50 alphanumeric chars)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  description = "Azure region; defaults to resource group location when null"
  type        = string
  default     = null
}

variable "sku" {
  description = "ACR pricing tier: Basic | Standard | Premium"
  type        = string
  default     = "Basic"
}

variable "tags" {
  type    = map(string)
  default = {}
}
