provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

resource "azurerm_resource_group" "rag_chatbot" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_storage_account" "storage" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.rag_chatbot.name
  location                 = azurerm_resource_group.rag_chatbot.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "documents" {
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.storage.id
  container_access_type = "private"
}

resource "azurerm_container_registry" "acr" {
  name                = var.container_registry  # Must be unique globally
  resource_group_name = azurerm_resource_group.rag_chatbot.name
  location            = azurerm_resource_group.rag_chatbot.location
  sku                 = "Basic"
  admin_enabled       = true
}

resource "azurerm_service_plan" "plan" {
  name                = var.service_plan_name
  location            = azurerm_resource_group.rag_chatbot.location
  resource_group_name = azurerm_resource_group.rag_chatbot.name
  os_type             = var.os_type
  sku_name            = var.sku_name
}

resource "azurerm_app_service" "api" {
  name                = var.app_service_name # Must be globally unique
  location            = azurerm_resource_group.rag_chatbot.location
  resource_group_name = azurerm_resource_group.rag_chatbot.name
  app_service_plan_id = azurerm_service_plan.plan.id
  site_config {
    linux_fx_version = "DOCKER|${azurerm_container_registry.acr.login_server}/rag-chatbot-api:latest"
  }

  app_settings = {
    "DOCKER_REGISTRY_SERVER_URL"      = "https://${azurerm_container_registry.acr.login_server}"
    "DOCKER_REGISTRY_SERVER_USERNAME" = azurerm_container_registry.acr.admin_username
    "DOCKER_REGISTRY_SERVER_PASSWORD" = azurerm_container_registry.acr.admin_password
  }

  depends_on = [azurerm_container_registry.acr]
}

resource "azurerm_app_service" "frontend" {
  name                = "${var.app_service_name}-frontend"
  location            = azurerm_resource_group.rag_chatbot.location
  resource_group_name = azurerm_resource_group.rag_chatbot.name
  app_service_plan_id = azurerm_service_plan.plan.id # Reuse existing plan

  site_config {
    linux_fx_version = "DOCKER|${azurerm_container_registry.acr.login_server}/rag-chatbot-frontend:latest"
  }

  app_settings = {
    "DOCKER_REGISTRY_SERVER_URL"      = "https://${azurerm_container_registry.acr.login_server}"
    "DOCKER_REGISTRY_SERVER_USERNAME" = azurerm_container_registry.acr.admin_username
    "DOCKER_REGISTRY_SERVER_PASSWORD" = azurerm_container_registry.acr.admin_password
    "REACT_APP_API_URL"               = "https://${azurerm_app_service.api.default_site_hostname}"
  }

  depends_on = [azurerm_container_registry.acr]
}

output "app_service_url" {
  value = azurerm_app_service.api.default_site_hostname
}

output "storage_connection_string" {
  value     = azurerm_storage_account.storage.primary_connection_string
  sensitive = true
}

output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "acr_admin_username" {
  value = azurerm_container_registry.acr.admin_username
}

output "acr_admin_password" {
  value     = azurerm_container_registry.acr.admin_password
  sensitive = true
}

output "frontend_url" {
  value = azurerm_app_service.frontend.default_site_hostname
}