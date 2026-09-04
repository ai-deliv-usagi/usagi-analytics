<#
.SYNOPSIS
  Sync local broadcast JSONL logs to the stream-health GCS prefix.

.DESCRIPTION
  Run this on the streaming PC (via Windows Task Scheduler, on a daily
  schedule that finishes before the "usagi-analytics-daily-stream-health"
  Cloud Scheduler job fires). Requires the gcloud CLI to be installed and
  authenticated (`gcloud auth login` or a service account via
  `gcloud auth activate-service-account`) with write access to the bucket.

  BroadcastLogger writes one JSONL file per broadcast and never modifies
  it again after the stream ends, so by default this script only uploads
  files whose last-write time falls within the last -Days day(s) (i.e.
  yesterday's stream) instead of re-scanning/re-comparing the entire
  history every run. Pass -All to fall back to a full rsync of the whole
  directory (useful for a one-off backfill or catch-up after downtime).

.PARAMETER BroadcastLogDir
  Directory containing the *.jsonl files written by BroadcastLogger
  (matches the ai-delivery BROADCAST_LOG_DIR env var). Defaults to the
  BROADCAST_LOG_DIR environment variable, falling back to "logs".

.PARAMETER BucketName
  Target GCS bucket name. Defaults to the STREAM_HEALTH_BUCKET_NAME
  environment variable.

.PARAMETER Days
  Only upload *.jsonl files last written within this many days. Default 1
  (i.e. yesterday's broadcast). Ignored when -All is passed.

.PARAMETER All
  Do a full rsync of BroadcastLogDir instead of the recent-files-only
  upload. Slower as history grows; use for backfills/catch-up.

.PARAMETER NamePrefix
  Only sync files whose name starts with this prefix (e.g.
  "@ai_deliv_usagi_20260711_180315.jsonl"). Defaults to
  "@ai_deliv_usagi_".

.PARAMETER ExcludeDirName
  Skip any file under a subfolder with this name (e.g. BroadcastLogDir's
  "post_stream" subfolder, which holds post-processing output rather than
  raw broadcast logs). Defaults to "post_stream".
#>
param(
    [string]$BroadcastLogDir = $(if ($env:BROADCAST_LOG_DIR) { $env:BROADCAST_LOG_DIR } else { "logs" }),
    [string]$BucketName = $env:STREAM_HEALTH_BUCKET_NAME,
    [int]$Days = 1,
    [switch]$All,
    [string]$NamePrefix = "@ai_deliv_usagi_",
    [string]$ExcludeDirName = "post_stream"
)

if (-not $BucketName) {
    throw "BucketName is required (pass -BucketName or set STREAM_HEALTH_BUCKET_NAME)."
}

if (-not (Test-Path $BroadcastLogDir)) {
    throw "BroadcastLogDir not found: $BroadcastLogDir"
}

$destination = "gs://$BucketName/stream_health/raw/"
$namePattern = "$NamePrefix*.jsonl"

if ($All) {
    Write-Host "Syncing (full) $BroadcastLogDir -> $destination"
    $excludeDirPattern = [regex]::Escape($ExcludeDirName)
    $excludePrefixPattern = [regex]::Escape($NamePrefix)
    $excludePattern = "(^|/)$excludeDirPattern(/|`$)|(^|/)(?!$excludePrefixPattern)[^/]*`$"
    # gsutil resolves to gsutil.cmd on Windows, which PowerShell invokes via cmd.exe;
    # without literal quotes here, cmd.exe treats the "|" in the regex as a pipe.
    $excludePatternArg = '"' + $excludePattern + '"'
    gsutil -m rsync -r -x $excludePatternArg $BroadcastLogDir $destination
    exit $LASTEXITCODE
}

$cutoff = (Get-Date).AddDays(-$Days)
$files = @(Get-ChildItem -Path $BroadcastLogDir -Recurse -File -Filter $namePattern |
    Where-Object {
        $_.LastWriteTime -ge $cutoff -and
        $_.DirectoryName.Split([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) -notcontains $ExcludeDirName
    })

if ($files.Count -eq 0) {
    Write-Host "No '$namePattern' files modified in the last $Days day(s) under $BroadcastLogDir; nothing to sync."
    exit 0
}

Write-Host "Syncing $($files.Count) '$namePattern' file(s) modified in the last $Days day(s) from $BroadcastLogDir -> $destination"
gsutil -m cp ($files | ForEach-Object { $_.FullName }) $destination
