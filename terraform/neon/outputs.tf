output "project_id" {
  description = "Neon project ID"
  value       = neon_project.flashsales.id
}

output "database_host" {
  description = "Neon database hostname"
  value       = neon_project.flashsales.database_host
}

output "database_url" {
  description = "Full DATABASE_URL connection string"
  value       = local.database_url
  sensitive   = true
}

output "database_user" {
  description = "Neon database username"
  value       = neon_project.flashsales.database_user
  sensitive   = true
}

output "database_password" {
  description = "Neon database password"
  value       = neon_project.flashsales.database_password
  sensitive   = true
}

output "database_name" {
  description = "Neon database name"
  value       = neon_project.flashsales.database_name
  sensitive   = true
}
