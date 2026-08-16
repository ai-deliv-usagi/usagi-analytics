output "artifact_registry_repository" {
  description = "Artifact Registry repository name."
  value       = google_artifact_registry_repository.app.name
}

output "image_build_command" {
  description = "Command to build and push the container image expected by the image variable."
  value       = "gcloud builds submit --tag ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}/${var.service_name}:latest"
}

output "cloud_run_url" {
  description = "Cloud Run service URL."
  value       = google_cloud_run_v2_service.app.uri
}

output "oauth_callback_url" {
  description = "Cloud Run OAuth callback endpoint. Put this into callback/callback.html."
  value       = "${google_cloud_run_v2_service.app.uri}/oauth/callback"
}

output "run_fetch_url" {
  description = "Cloud Scheduler target URL."
  value       = "${google_cloud_run_v2_service.app.uri}/run-fetch"
}

output "snapshot_bucket" {
  description = "GCS bucket where JSONL snapshots are stored."
  value       = google_storage_bucket.snapshots.name
}
