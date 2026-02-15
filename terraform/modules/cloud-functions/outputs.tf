output "function_name" {
  description = "Cloud Function name"
  value       = google_cloudfunctions2_function.document_ingestion.name
}

output "function_url" {
  description = "Cloud Function HTTPS trigger URL"
  value       = google_cloudfunctions2_function.document_ingestion.url
}
