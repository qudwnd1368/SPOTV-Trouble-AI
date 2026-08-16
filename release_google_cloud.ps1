param(
    [Parameter(Mandatory = $true)] [string] $ProjectId,
    [Parameter(Mandatory = $true)] [string] $OAuthClientId,
    [Parameter(Mandatory = $true)] [string] $AllowedEmails,
    [string] $Region = "asia-northeast3",
    [string] $ServiceName = "spotv-trouble-ai"
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "Google Cloud CLI (gcloud) is required: https://cloud.google.com/sdk/docs/install"
}

gcloud config set project $ProjectId
$serviceAccountEmail = "$ServiceName-runtime@$ProjectId.iam.gserviceaccount.com"
$serviceUrl = gcloud run services describe $ServiceName --project $ProjectId --region $Region --format "value(status.url)"

$oauthSecretSecure = Read-Host "OAuth client secret" -AsSecureString
$adminPasswordSecure = Read-Host "Administrator password" -AsSecureString
$oauthSecret = [System.Net.NetworkCredential]::new("", $oauthSecretSecure).Password
$adminPassword = [System.Net.NetworkCredential]::new("", $adminPasswordSecure).Password
$cookieBytes = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Fill($cookieBytes)
$cookieSecret = [Convert]::ToBase64String($cookieBytes)

function Set-GoogleSecret([string] $Name, [string] $Value) {
    gcloud secrets describe $Name --project $ProjectId 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        gcloud secrets create $Name --replication-policy automatic --project $ProjectId | Out-Null
    }
    $temporaryFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($temporaryFile, $Value, [System.Text.UTF8Encoding]::new($false))
        gcloud secrets versions add $Name --data-file $temporaryFile --project $ProjectId | Out-Null
    }
    finally {
        Remove-Item -LiteralPath $temporaryFile -Force -ErrorAction SilentlyContinue
    }
    gcloud secrets add-iam-policy-binding $Name --member "serviceAccount:$serviceAccountEmail" --role "roles/secretmanager.secretAccessor" --project $ProjectId --quiet | Out-Null
}

Set-GoogleSecret "spotv-oauth-client-secret" $oauthSecret
Set-GoogleSecret "spotv-cookie-secret" $cookieSecret
Set-GoogleSecret "spotv-admin-password" $adminPassword
$oauthSecret = $null
$adminPassword = $null

gcloud run deploy $ServiceName `
    --source . `
    --project $ProjectId `
    --region $Region `
    --service-account $serviceAccountEmail `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min 0 `
    --max 2 `
    --set-env-vars "DATABASE_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=$ProjectId,ENABLE_GOOGLE_LOGIN=true,APP_URL=$serviceUrl,OAUTH_CLIENT_ID=$OAuthClientId,ALLOWED_EMAILS=$AllowedEmails" `
    --set-secrets "OAUTH_CLIENT_SECRET=spotv-oauth-client-secret:latest,COOKIE_SECRET=spotv-cookie-secret:latest,ADMIN_PASSWORD=spotv-admin-password:latest"

Write-Host "SPOTV Tech Copilot is live: $serviceUrl" -ForegroundColor Green
