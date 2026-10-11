# Stores the app's API keys and access token in AWS Secrets Manager (DEPLOYMENT.md step 4).
#
#   $env:AWS_PROFILE = "<your-sso-profile>"
#   powershell -ExecutionPolicy Bypass -File infra\scripts\set-secrets.ps1
#
# Asks for each key (input hidden; press Enter to skip), keeps any value already stored when you skip,
# creates the access token once and reuses it on later runs. Key values are never printed; the access
# token is printed at the end because you type it into the app's login screen.

param([string]$SecretId = "policy-analytics/app")
$ErrorActionPreference = "Stop"

function Test-Real([string]$value) { return $value -and ($value -notlike "*REPLACE_ME*") }

function Read-Hidden([string]$prompt) {
    $secure = Read-Host -Prompt $prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

Write-Host "Checking your AWS login..."
aws sts get-caller-identity --query Arn --output text
if ($LASTEXITCODE -ne 0) { throw "Not logged in to AWS. Run: aws sso login --profile <your-sso-profile>" }

$current = aws secretsmanager get-secret-value --secret-id $SecretId --query SecretString --output text | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "Could not read secret $SecretId. Did 'make aws-apply' finish?" }

$keys = [ordered]@{
    OPENAI_API_KEY      = "OpenAI API key (sk-...)"
    GOOGLE_API_KEY      = "Google Gemini API key (AIza...)"
    LANGFUSE_PUBLIC_KEY = "Langfuse public key (pk-lf-...)"
    LANGFUSE_SECRET_KEY = "Langfuse secret key (sk-lf-...)"
    TAVILY_API_KEY      = "Tavily API key (tvly-...)"
}
$new = [ordered]@{}
Write-Host ""
Write-Host "For each key: paste it and press Enter, or just press Enter to skip. Typing is hidden."
foreach ($name in $keys.Keys) {
    $stored = $current.$name
    $hint = if (Test-Real $stored) { "already set - Enter keeps it" } else { "not set - Enter skips" }
    if ($name -eq "OPENAI_API_KEY" -and -not (Test-Real $stored) -and (Test-Real $env:OPENAI_API_KEY)) {
        $use = Read-Host "OpenAI key found in your Windows environment. Use it? (Y/n)"
        if ($use -notmatch "^[nN]") { $new[$name] = $env:OPENAI_API_KEY; continue }
    }
    $typed = Read-Hidden "$($keys[$name]) [$hint]"
    $new[$name] = if ($typed) { $typed } elseif (Test-Real $stored) { $stored } else { $current.$name }
}

# The login token for the deployed app: created once, kept on later runs.
if (Test-Real $current.APP_ACCESS_TOKEN) {
    $new["APP_ACCESS_TOKEN"] = $current.APP_ACCESS_TOKEN
} else {
    $bytes = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $new["APP_ACCESS_TOKEN"] = -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

# UTF-8 without a byte-order mark (Windows PowerShell's Set-Content would add one and break the JSON).
$path = Join-Path ([IO.Path]::GetTempPath()) ("secrets-" + [guid]::NewGuid() + ".json")
try {
    [IO.File]::WriteAllText($path, ($new | ConvertTo-Json -Compress))
    aws secretsmanager put-secret-value --secret-id $SecretId --secret-string "file://$path" --query Name --output text
    if ($LASTEXITCODE -ne 0) { throw "Upload failed." }
} finally {
    Remove-Item $path -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Saved to $SecretId :"
foreach ($name in $new.Keys) {
    $state = if (Test-Real $new[$name]) { "set" } else { "not set (feature off)" }
    Write-Host ("  {0,-20} {1}" -f $name, $state)
}
Write-Host ""
Write-Host "Your app login token (save it in a password manager):"
Write-Host "  $($new['APP_ACCESS_TOKEN'])" -ForegroundColor Yellow
