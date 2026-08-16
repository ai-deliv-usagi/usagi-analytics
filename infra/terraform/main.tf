provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  artifact_repository_id  = "usagi-analytics"
  tiktok_client_key_id    = "tiktok-client-key"
  tiktok_client_secret_id = "tiktok-client-secret"
  tiktok_token_id         = "tiktok-display-api-token"
  run_fetch_token_id      = "usagi-run-fetch-token"
  storage_bucket_name     = coalesce(var.storage_bucket_name, "${var.project_id}-${var.service_name}-snapshots")
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = local.artifact_repository_id
  description   = "Docker images for usagi-analytics"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "cloud_run" {
  account_id   = "${var.service_name}-run"
  display_name = "usagi-analytics Cloud Run runtime"

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "tiktok_client_key" {
  secret_id = local.tiktok_client_key_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "tiktok_client_secret" {
  secret_id = local.tiktok_client_secret_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "tiktok_token" {
  secret_id = local.tiktok_token_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "run_fetch_token" {
  secret_id = local.run_fetch_token_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "tiktok_client_key" {
  count       = var.tiktok_client_key == null ? 0 : 1
  secret      = google_secret_manager_secret.tiktok_client_key.id
  secret_data = var.tiktok_client_key
}

resource "google_secret_manager_secret_version" "tiktok_client_secret" {
  count       = var.tiktok_client_secret == null ? 0 : 1
  secret      = google_secret_manager_secret.tiktok_client_secret.id
  secret_data = var.tiktok_client_secret
}

resource "random_password" "run_fetch_token" {
  length  = 40
  special = false
}

resource "google_secret_manager_secret_version" "run_fetch_token" {
  secret      = google_secret_manager_secret.run_fetch_token.id
  secret_data = random_password.run_fetch_token.result
}

resource "google_secret_manager_secret_iam_member" "cloud_run_secret_accessor" {
  for_each = {
    tiktok_client_key    = google_secret_manager_secret.tiktok_client_key.secret_id
    tiktok_client_secret = google_secret_manager_secret.tiktok_client_secret.secret_id
    tiktok_token         = google_secret_manager_secret.tiktok_token.secret_id
    run_fetch_token      = google_secret_manager_secret.run_fetch_token.secret_id
  }

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_secret_manager_secret_iam_member" "cloud_run_token_version_adder" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.tiktok_token.secret_id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_storage_bucket" "snapshots" {
  name                        = local.storage_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "cloud_run_snapshot_writer" {
  bucket = google_storage_bucket.snapshots.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_cloud_run_v2_service" "app" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      image = var.image

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "TOKEN_STORE_BACKEND"
        value = "secret_manager"
      }

      env {
        name  = "TOKEN_SECRET_ID"
        value = google_secret_manager_secret.tiktok_token.secret_id
      }

      env {
        name  = "STORAGE_BACKEND"
        value = "gcs_jsonl"
      }

      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.snapshots.name
      }

      env {
        name  = "TIKTOK_REDIRECT_URI"
        value = var.tiktok_redirect_uri
      }

      env {
        name = "TIKTOK_CLIENT_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.tiktok_client_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "TIKTOK_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.tiktok_client_secret.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "RUN_FETCH_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.run_fetch_token.secret_id
            version = "latest"
          }
        }
      }

      ports {
        container_port = 8080
      }
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.cloud_run_secret_accessor,
    google_secret_manager_secret_version.tiktok_client_key,
    google_secret_manager_secret_version.tiktok_client_secret,
    google_secret_manager_secret_version.run_fetch_token,
    google_storage_bucket_iam_member.cloud_run_snapshot_writer,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_scheduler_job" "daily_fetch" {
  name        = "${var.service_name}-daily-fetch"
  description = "Fetch TikTok video metrics for usagi-analytics"
  region      = var.region
  schedule    = var.scheduler_schedule
  time_zone   = var.scheduler_time_zone

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.app.uri}/run-fetch"
    headers = {
      "X-Usagi-Run-Token" = random_password.run_fetch_token.result
    }
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.public_invoker,
    google_secret_manager_secret_version.run_fetch_token,
  ]
}
