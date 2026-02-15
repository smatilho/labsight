output "uploads_bucket_name" {
  description = "Name of the uploads GCS bucket"
  value       = google_storage_bucket.uploads.name
}

output "uploads_bucket_url" {
  description = "URL of the uploads GCS bucket"
  value       = google_storage_bucket.uploads.url
}

output "function_artifacts_bucket_name" {
  description = "Name of the function artifacts GCS bucket"
  value       = google_storage_bucket.function_artifacts.name
}

output "chromadb_bucket_name" {
  description = "Name of the ChromaDB persistence GCS bucket"
  value       = google_storage_bucket.chromadb.name
}

output "docker_registry_url" {
  description = "Artifact Registry Docker repository URL"
  value       = "${google_artifact_registry_repository.docker.location}-docker.pkg.dev/${google_artifact_registry_repository.docker.project}/${google_artifact_registry_repository.docker.repository_id}"
}
