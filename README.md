# usagi-analytics

認証済みTikTokアカウントの投稿メトリクスを、TikTok Display API `/v2/video/list/` から定期取得して蓄積するバッチ分析プロジェクトです。実況システム本体とは切り離し、Cloud Run + Cloud Schedulerで1日1回程度の実行を想定します。

## セットアップ

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
```

最低限必要な環境変数:

```powershell
$env:TIKTOK_CLIENT_KEY = "your-client-key"
$env:TIKTOK_CLIENT_SECRET = "your-client-secret"
$env:TIKTOK_REDIRECT_URI = "https://<your-github-pages>/callback.html"
$env:TIKTOK_CLOUD_RUN_CALLBACK_URL = "https://<cloud-run-url>/oauth/callback"
$env:TOKEN_STORE_BACKEND = "file" # local debug. production should use secret_manager
$env:TOKEN_FILE_PATH = ".local/tiktok_token.json"
$env:SQLITE_DB_PATH = ".local/usagi_analytics.sqlite3"
```

Secret Managerを使う場合:

```powershell
$env:TOKEN_STORE_BACKEND = "secret_manager"
$env:GCP_PROJECT_ID = "your-gcp-project"
$env:TOKEN_SECRET_ID = "tiktok-display-api-token"
```

Secret ManagerのシークレットはJSONとして保存されます。Cloud Runのサービスアカウントには対象シークレットへの読み書き権限を付与してください。

## OAuth初回認可

1. TikTok Developer PortalでLogin Kit / Display APIを有効化し、`video.list` を承認します。
2. TikTokのRedirect URIにGitHub Pagesの `docs/callback.html` 公開URLを登録します。
3. `docs/callback.js` 内の `window.USAGI_ANALYTICS_CALLBACK_URL` をCloud Runの `/oauth/callback` URLに設定してGitHub Pagesへ配置します。
4. 認可URLを生成します。

```powershell
python -m src.main auth-url
```

5. 表示されたURLをブラウザで開き、対象TikTokアカウントで認可します。
6. TikTokからGitHub Pagesへ戻った後、ページがCloud Run `/oauth/callback` に認可コードを転送します。
7. Cloud Run側が認可コードをアクセストークン/リフレッシュトークンへ交換し、トークンストアへ保存します。

ローカルで交換だけ試す場合:

```powershell
python -m src.main exchange --code "<authorization-code>"
```

## 全動画取得バッチ

ローカル手動実行:

```powershell
python -m src.main fetch
```

Cloud Run HTTP実行:

```http
POST /run-fetch
```

成功時はSQLiteの `video_snapshots` に、同一動画IDでも毎回別スナップショットとして保存されます。

## 動作確認手順

1. SandboxアプリとSandbox専用TikTokアカウントでOAuth初回認可を完了します。
2. `python -m src.main fetch` を実行します。
3. SQLiteを確認します。

```powershell
python -m src.main stats
```

`snapshots` が保存件数、`distinct_videos` が取得できた動画ID数です。本番アプリに切り替える場合は、対象アカウントで同じ手順を実行し、TikTokインサイトの投稿数と `distinct_videos` を照合してください。

## Cloud Run

起動コマンド例:

```powershell
python -m src.main serve
```

コンテナでは `PORT` 環境変数があればそのポートでHTTPサーバを起動します。Cloud Schedulerからは `/run-fetch` にPOSTしてください。

## Terraform

`infra/terraform` で以下を作成します。

- Secret Manager: TikTok client key / client secret / OAuth token / Scheduler token
- Artifact Registry
- Cloud Run service
- Cloud Scheduler job
- GCS bucket: `video_snapshots/YYYY/MM/DD/*.jsonl` に取得履歴を保存
- Cloud Run用Service AccountとIAM

初回の流れ:

```powershell
cd infra/terraform
copy terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` の `project_id`, `tiktok_redirect_uri`, `image`, `tiktok_client_key`, `tiktok_client_secret` を設定します。

注意: `tiktok_client_key` / `tiktok_client_secret` をTerraformでSecret Managerへ投入すると、値はTerraform stateにも残ります。stateを安全なGCS backend等で管理してください。stateに入れたくない場合は、TerraformではSecretの箱だけ作り、Secret Versionは別途 `gcloud secrets versions add` で追加してください。

Artifact Registryを先に作るため、初回だけtarget applyします。

```powershell
terraform init
terraform apply "-target=google_artifact_registry_repository.app"
```

イメージをbuild/pushします。

```powershell
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/<project-id>/usagi-analytics/usagi-analytics:latest
```

`terraform.tfvars` の `image` がそのURIになっていることを確認して、再度applyします。

```powershell
terraform apply
terraform output oauth_callback_url
```

出力された `oauth_callback_url` を `docs/callback.js` の `USAGI_ANALYTICS_CALLBACK_URL` に設定してGitHub Pagesへ配置します。その後、TikTok Developer PortalにはGitHub Pages側の `callback.html` URLをRedirect URIとして登録してください。

## TikTok申請URL

GitHub Pagesで `docs/` を公開する場合、TikTok Developer Portalには以下を指定します。

- Privacy Policy URL: `https://<your-github-pages-domain>/privacy.html`
- Terms URL: `https://<your-github-pages-domain>/terms.html`
- Web/Desktop URL: `https://<your-github-pages-domain>/`
- Redirect URI: `https://<your-github-pages-domain>/callback.html`

GitHub PagesのSourceは、このリポジトリの `docs/` ディレクトリを指定してください。`docs/callback.js` の `USAGI_ANALYTICS_CALLBACK_URL` は、Terraform outputの `oauth_callback_url` に置き換えます。

## 取得フィールド

`id,title,create_time,view_count,like_count,comment_count,share_count,video_description,duration,share_url`

TikTok Display APIの仕様上、未指定フィールドは返らないため、常に明示指定します。
