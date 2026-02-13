output "uploads_bucket_name" {
  description = "Name of the uploads GCS bucket"
  value       = google_storage_bucket.uploads.name
}

output "uploads_bucket_url" {
  description = "URL of the uploads GCS bucket"
  value       = google_storage_bucket.uploads.url
}
