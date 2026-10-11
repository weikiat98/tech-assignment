#!/usr/bin/env bash
# macOS/Linux equivalent of set-secrets.ps1: stores the app's API keys and access token in AWS Secrets
# Manager (DEPLOYMENT.md step 4). Needs the AWS CLI, jq and openssl.
#
#   export AWS_PROFILE=<your-sso-profile>
#   bash infra/scripts/set-secrets.sh
#
# Asks for each key (input hidden; press Enter to skip), keeps any value already stored when you skip,
# creates the access token once and reuses it on later runs. Key values are never printed; the access
# token is printed at the end because you type it into the app's login screen.
set -euo pipefail
SECRET_ID="${1:-policy-analytics/app}"

is_real() { [[ -n "${1:-}" && "$1" != *REPLACE_ME* ]]; }

echo "Checking your AWS login..."
aws sts get-caller-identity --query Arn --output text \
  || { echo "Not logged in to AWS. Run: aws sso login --profile <your-sso-profile>" >&2; exit 1; }
current=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --query SecretString --output text) \
  || { echo "Could not read secret $SECRET_ID. Did 'make aws-apply' finish?" >&2; exit 1; }

new='{}'
echo
echo "For each key: paste it and press Enter, or just press Enter to skip. Typing is hidden."
for name in OPENAI_API_KEY GOOGLE_API_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY TAVILY_API_KEY; do
  stored=$(jq -r --arg k "$name" '.[$k] // ""' <<<"$current")
  if is_real "$stored"; then hint="already set - Enter keeps it"; else hint="not set - Enter skips"; fi
  read -r -s -p "$name [$hint]: " typed; echo
  typed="${typed//[[:space:]]/}"
  if [[ -n "$typed" ]]; then value="$typed"; else value="$stored"; fi
  new=$(jq -c --arg k "$name" --arg v "$value" '. + {($k): $v}' <<<"$new")
done

token=$(jq -r '.APP_ACCESS_TOKEN // ""' <<<"$current")
is_real "$token" || token=$(openssl rand -hex 24)
new=$(jq -c --arg v "$token" '. + {APP_ACCESS_TOKEN: $v}' <<<"$new")

tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
printf '%s' "$new" > "$tmp"
aws secretsmanager put-secret-value --secret-id "$SECRET_ID" --secret-string "file://$tmp" --query Name --output text

echo
echo "Saved to $SECRET_ID :"
jq -r 'to_entries[] | "  \(.key)\t\(if (.value == "" or (.value | contains("REPLACE_ME"))) then "not set (feature off)" else "set" end)"' <<<"$new"
echo
echo "Your app login token (save it in a password manager):"
echo "  $token"
