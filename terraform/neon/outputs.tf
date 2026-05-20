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
