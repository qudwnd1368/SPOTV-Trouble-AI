param(
    [Parameter(Mandatory = $true)] [string] $ProjectId,
    [string] $Region = "asia-northeast3",
    [string] $ServiceName = "spotv-trouble-ai"
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "Google Cloud CLI (gcloud) is required: https://cloud.google.com/sdk/docs/install"
}

gcloud config set project $ProjectId
gcloud services enable run.googleapis.com firestore.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com iam.googleapis.com

$serviceAccountName = "$ServiceName-runtime"
$serviceAccountEmail = "$serviceAccountName@$ProjectId.iam.gserviceaccount.com"
$existingAccount = gcloud iam service-accounts describe $serviceAccountEmail --project $ProjectId 2>$null
if ($LASTEXITCODE -ne 0) {
    gcloud iam service-accounts create $serviceAccountName --project $ProjectId --display-name "SPOTV Tech Copilot runtime"
}

gcloud projects add-iam-policy-binding $ProjectId --member "serviceAccount:$serviceAccountEmail" --role "roles/datastore.user" --quiet

$databaseExists = gcloud firestore databases describe --database "(default)" --project $ProjectId 2>$null
if ($LASTEXITCODE -ne 0) {
    gcloud firestore databases create --database "(default)" --location $Region --type firestore-native --project $ProjectId --quiet
}

gcloud run deploy $ServiceName `
    --source . `
    --project $ProjectId `
    --region $Region `
    --service-account $serviceAccountEmail `
    --no-allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min 0 `
    --max 2 `
    --set-env-vars "DATABASE_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=$ProjectId,ENABLE_GOOGLE_LOGIN=false"

$serviceUrl = gcloud run services describe $ServiceName --project $ProjectId --region $Region --format "value(status.url)"
Write-Host "Private bootstrap deployment complete." -ForegroundColor Green
Write-Host "Service URL: $serviceUrl"
Write-Host "OAuth redirect URI: $serviceUrl/oauth2callback" -ForegroundColor Yellow
Write-Host "Create a Google OAuth Web client with this redirect URI before public release."
