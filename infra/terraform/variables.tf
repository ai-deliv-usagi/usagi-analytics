variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run, Scheduler, and Artifact Registry."
  type        = string
  default     = "asia-northeast1"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "usagi-analytics"
}

variable "image" {
  description = "Container image URI to deploy to Cloud Run."
  type        = string
}

variable "tiktok_redirect_uri" {
  description = "GitHub Pages callback.html URL registered in TikTok Developer Portal."
  type        = string
}

variable "tiktok_client_key" {
  description = "TikTok client key. If set, Terraform creates the initial Secret Manager version."
  type        = string
  sensitive   = true
  default     = null
}

variable "tiktok_client_secret" {
  description = "TikTok client secret. If set, Terraform creates the initial Secret Manager version."
  type        = string
  sensitive   = true
  default     = null
}

variable "scheduler_schedule" {
  description = "Cloud Scheduler cron expression."
  type        = string
  default     = "0 4 * * *"
}

variable "scheduler_time_zone" {
  description = "Cloud Scheduler time zone."
  type        = string
  default     = "Asia/Tokyo"
}

variable "storage_bucket_name" {
  description = "GCS bucket for JSONL video snapshots. Defaults to <project_id>-<service_name>-snapshots."
  type        = string
  default     = null
}

variable "min_instance_count" {
  description = "Cloud Run minimum instance count."
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Cloud Run maximum instance count."
  type        = number
  default     = 1
}
