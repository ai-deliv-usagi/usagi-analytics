<#
.SYNOPSIS
  Sync local broadcast JSONL logs to the stream-health GCS prefix.

.DESCRIPTION
  Run this on the streaming PC (via Windows Task Scheduler, on a daily
  schedule that finishes before the "usagi-analytics-daily-stream-health"
  Cloud Scheduler job fires). Requires the gcloud CLI to be installed and
  authenticated (`gcloud auth login` or a service account via
  `gcloud auth activate-service-account`) with write access to the bucket.

.PARAMETER BroadcastLogDir
  Directory containing the *.jsonl files written by BroadcastLogger
  (matches the ai-delivery BROADCAST_LOG_DIR env var). Defaults to the
  BROADCAST_LOG_DIR environment variable, falling back to "logs".

.PARAMETER BucketName
  Target GCS bucket name. Defaults to the STREAM_HEALTH_BUCKET_NAME
  environment variable.
#>
param(
    [string]$BroadcastLogDir = $(if ($env:BROADCAST_LOG_DIR) { $env:BROADCAST_LOG_DIR } else { "logs" }),
    [string]$BucketName = $env:STREAM_HEALTH_BUCKET_NAME
)

if (-not $BucketName) {
    throw "BucketName is required (pass -BucketName or set STREAM_HEALTH_BUCKET_NAME)."
}

if (-not (Test-Path $BroadcastLogDir)) {
    throw "BroadcastLogDir not found: $BroadcastLogDir"
}

$destination = "gs://$BucketName/stream_health/raw/"
Write-Host "Syncing $BroadcastLogDir -> $destination"
gsutil -m rsync -r $BroadcastLogDir $destination
