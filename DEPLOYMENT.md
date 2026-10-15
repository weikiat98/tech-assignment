# Deployment

| Environment | Where | LLM | Data | Tracing |
|---|---|---|---|---|
| local | `docker compose up` | `auto`: live when keys are set, else MockLLM | live sources, snapshot fallback | Langfuse if keys are set |
| ci | GitHub Actions | `mock` | snapshots only (`OFFLINE_MODE=true`) | off |
| aws | ECS Fargate behind CloudFront | `auto` with keys from Secrets Manager | live, snapshot fallback | Langfuse Cloud if keys are set |
| gcp (documented alternative) | Cloud Run | same | same | same |

## 1. Local (Docker Compose)

```bash
cp .env.example .env            # edit keys if you have them; placeholders run everything on MockLLM
docker compose up -d --build    # or: make up
```

| Service | Port | Notes |
|---|---|---|
| postgres | internal | `pgvector/pgvector:pg16`, volume `pgdata` |
| gotenberg | internal | Chromium HTML-to-PDF |
| migrate | n/a | `python -m app.db.init`: creates tables and seeds the internal mock data, then exits |
| api | 8000 | FastAPI; starts after migrate completes and postgres is healthy |
| frontend | 8080 | nginx serving the SPA and proxying `/api`, `/ws`, `/healthz`, `/readyz` to the api |

Secrets stay in `.env`, which is git-ignored; `.env.example` holds placeholders only. Change
`POSTGRES_PASSWORD` before exposing the database anywhere.

## 2. AWS (ECS Fargate): architecture

```
Internet ──HTTPS──▶ CloudFront (*.cloudfront.net certificate, no domain needed, WebSockets supported)
                        │ HTTP, only from CloudFront's managed prefix list
                        ▼
                      ALB ── /api/*, /ws/*, /healthz, /readyz ──▶ api service   [api + gotenberg sidecar]
                        └─── /* ───────────────────────────────▶ web service   [nginx + SPA]
                                                                     │
                                         private subnets, no internet ▼
                                                      RDS PostgreSQL 16 (db.t4g.micro)
```

- Region `ap-southeast-1`. Tasks run in public subnets with public IPs and security groups that accept
  traffic only from the ALB. That avoids a NAT gateway (about US$40/month). RDS sits in private subnets.
- Secrets live in AWS Secrets Manager and reach the task through the task definition's `secrets` block.
  The RDS master password is generated and stored by RDS (`manage_master_user_password`), so it never
  appears in Terraform state.
- The api service runs **exactly one task**: the in-process runner and event bus are single-replica
  (see ARCHITECTURE.md §8 for the scale-out path).
- `APP_ENV=aws` turns off the chaos admin endpoint. A shared `APP_ACCESS_TOKEN` protects `/api` and
  `/ws`, because the deployed app calls paid LLM APIs.
- Cost while running: about **US$3-4 a day** (Fargate ~2, ALB ~0.6, RDS ~0.7, public IPs/CloudFront/logs
  ~0.5). Paused: about US$1 a day. Terraform also creates an AWS Budget with email alerts at 50%, 80% and
  100% of `monthly_budget_usd`.

## 3. AWS step by step

Run everything from the repo root. Steps marked 💰 create billable resources.

**Which terminal to use**

| Your machine | Use | Why |
|---|---|---|
| Windows | **Git Bash** (installed with [Git for Windows](https://git-scm.com/download/win)) for everything, except the one PowerShell option in step 4 | `make aws-deploy`, `aws-pause` and `aws-resume` run `bash infra/scripts/*.sh`. In PowerShell or cmd, `bash` is not on PATH, so they fail with *"The system cannot find the file specified"*. |
| macOS | **Terminal** (zsh or bash) for everything | `bash` is built in; nothing else is needed. |

| Command | Windows | macOS |
|---|---|---|
| `make aws-plan`, `make aws-apply`, `make aws-destroy` (only call `terraform`) | Git Bash (PowerShell also works) | Terminal |
| `make aws-deploy`, `make aws-pause`, `make aws-resume` (call `bash infra/scripts/*.sh`) | **Git Bash only** | Terminal |
| `bash infra/scripts/set-secrets.sh` (step 4) | Git Bash | Terminal |
| `infra\scripts\set-secrets.ps1` (step 4) | **PowerShell only** | not applicable |
| `aws ...`, `terraform ...`, `cp`, `cat`, `rm` snippets | Git Bash (the `cp`/`cat`/`rm` and `export` snippets don't run in PowerShell) | Terminal |

The code blocks below are bash unless labelled `powershell`. The `export AWS_PROFILE=...` line is bash;
the PowerShell equivalent is `$env:AWS_PROFILE = "<your-sso-profile>"`, and the variable only applies
to the shell window it was set in, so set it again in every new window.

**Check before you start** (Git Bash on Windows): `bash --version`, `make --version`, `aws --version`
and `terraform version` should all print a version. If `make` is not found in Git Bash, install it
(`winget install ezwinports.make`) and reopen the terminal.

**Every AWS command below (`make aws-*`, `terraform`, `aws ...`, `infra/scripts/*`) uses the AWS CLI's
*current* profile, not necessarily your SSO one.** If `AWS_PROFILE` is unset they fall back to the
`default` profile, which on many machines holds a stale access key and fails with
`InvalidClientTokenId`. In **every new shell**, before step 2:

```bash
# Git Bash (Windows) / Terminal (macOS)
export AWS_PROFILE=<your-sso-profile>     # PowerShell: $env:AWS_PROFILE = "<your-sso-profile>"
aws sts get-caller-identity               # sanity check: must show your SSO AdministratorAccess ARN
```

### Step 0: prerequisites (once)

**macOS (Terminal):** install the tools with [Homebrew](https://brew.sh) (Docker Desktop must be running
before step 5):

```bash
brew install awscli terraform jq make
brew install --cask docker
```

**Windows (PowerShell, once):** install the tools, then close PowerShell and open **Git Bash** for
every later step:

```powershell
winget install Git.Git Amazon.AWSCLI Hashicorp.Terraform ezwinports.make jqlang.jq Docker.DockerDesktop
```

(If `brew install terraform` is refused, use HashiCorp's tap: `brew tap hashicorp/tap && brew install
hashicorp/tap/terraform`.) Apple Silicon Macs are fine: `deploy.sh` builds `linux/amd64` images, which is what
Fargate runs here.

Then verify (Git Bash on Windows, Terminal on macOS):

```bash
aws --version                  # AWS CLI v2
terraform version              # >= 1.6
docker version; jq --version; make --version

# Terraform, deploy.sh and pause.sh use the AWS CLI's current profile. With IAM Identity Center (SSO),
# select your profile in every new shell, and log in again when the session expires:
export AWS_PROFILE=<your-sso-profile>                               # PowerShell: $env:AWS_PROFILE = "<your-sso-profile>"
aws sso login                                                       # only when the session has expired
aws sts get-caller-identity                                         # must print your account and an AdministratorAccess ARN
aws configure get region                                            # must print ap-southeast-1 (lower case)
```

If `get-caller-identity` fails:

- `Credential should be scoped to a valid region`: the region is set in upper case. Run
  `aws configure set region ap-southeast-1 --profile <your-sso-profile>`.
- `InvalidClientTokenId` / `The security token included in the request is invalid`: usually
  `AWS_PROFILE` is not set in this shell, so the CLI is using the `default` profile and its stale access
  key. Run `export AWS_PROFILE=<your-sso-profile>` and retry (`aws configure list-profiles` shows what
  exists). If you do use access keys, the key is wrong, deleted or inactive: create a new access key for your IAM user (IAM → Users → Security
  credentials) and run `aws configure`, or use IAM Identity Center with `aws configure sso` and then
  `export AWS_PROFILE=<profile>`.

Also set monthly spending limits in the OpenAI and Google AI Studio consoles. They are the last line
of defence for the API keys you put in AWS.

### Step 1: configure Terraform (once)

```bash
cp infra/terraform/aws/terraform.tfvars.example infra/terraform/aws/terraform.tfvars
```

`terraform.tfvars.example` is the committed template; `terraform.tfvars` is your git-ignored copy, and the
only one Terraform reads (the `.example` file is ignored). Edit `terraform.tfvars`; the template's
`REPLACE_ME` values must all be replaced:

```hcl
github_repo        = "weikiat98/tech-assignment"   # owner/repo allowed to deploy via GitHub OIDC
github_owner_id    = ""                            # leave "" unless step 7's AssumeRole error says otherwise
github_repo_id     = ""
alert_email        = "you@example.com"             # AWS Budgets alerts (confirm the subscription email)
monthly_budget_usd = 30
langfuse_host      = "https://us.cloud.langfuse.com"  # US; EU is https://cloud.langfuse.com
```

### Step 2: plan (free, read-only)

Needs step 1 done and `AWS_PROFILE` set (see the top of this section): `plan` reads your AWS account.

```bash
make aws-plan        # terraform init -upgrade + plan -out tfplan
```

Review the plan: roughly 45 resources (VPC, subnets, security groups, ECR, RDS, Secrets Manager, IAM roles
incl. the GitHub OIDC provider, ALB, CloudFront, ECS cluster/services/task definitions, log groups,
budget), and **0 to destroy**.

### Step 3: apply 💰

```bash
make aws-apply       # applies exactly the reviewed plan; about 15-20 minutes (RDS and CloudFront are slow)
terraform -chdir=infra/terraform/aws output
```

The ECS services start with the image tag `bootstrap`, which doesn't exist yet. They keep retrying until
step 5 pushes real images. That is expected.

If your account already has a GitHub OIDC provider (from another project), the apply fails with
`EntityAlreadyExists`. Import it first:
`terraform -chdir=infra/terraform/aws import aws_iam_openid_connect_provider.github arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com`.

### Step 4: put the real secrets into Secrets Manager

Terraform creates the secret with placeholders only, so keys never enter Terraform state.

**Easiest on macOS/Linux (Terminal):** run the bash helper (needs `aws`, `jq`, `openssl`). It does the
same as the PowerShell one below:

```bash
export AWS_PROFILE=<your-sso-profile>
bash infra/scripts/set-secrets.sh
```

**Easiest on Windows (open PowerShell for this step only):** run the helper. It asks for each key with hidden typing (Enter skips),
creates the access token, uploads, deletes the temporary file, and prints the token:

```powershell
$env:AWS_PROFILE = "<your-sso-profile>"
powershell -ExecutionPolicy Bypass -File infra\scripts\set-secrets.ps1
```

**Manual (Git Bash on Windows, Terminal on macOS/Linux):** write the real values to a temporary file, upload, then delete it:

```bash
cat > secrets.json <<'EOF'   # on macOS, generate the token with: openssl rand -hex 24
{
  "OPENAI_API_KEY": "sk-...",
  "GOOGLE_API_KEY": "...",
  "LANGFUSE_PUBLIC_KEY": "pk-lf-...",
  "LANGFUSE_SECRET_KEY": "sk-lf-...",
  "TAVILY_API_KEY": "tvly-REPLACE_ME",
  "APP_ACCESS_TOKEN": "<a long random string, e.g. from: openssl rand -hex 24>"
}
EOF
aws secretsmanager put-secret-value --secret-id policy-analytics/app --secret-string file://secrets.json
rm secrets.json
```

Keep any key you don't have as its placeholder; that feature is then off. `APP_ACCESS_TOKEN` must be a
real value, because the URL is public; you type it into the app's token screen. ECS reads secrets
when a task starts, so after changing them later, roll the api with
`aws ecs update-service --cluster policy-analytics --service <api_service> --force-new-deployment`.

### Step 5: first deploy from your machine 💰

Git Bash on Windows (not PowerShell), Terminal on macOS:

```bash
export AWS_PROFILE=<your-sso-profile>   # if this is a new shell; also needs Docker running
make aws-deploy      # = bash infra/scripts/deploy.sh
```

The script reads everything from `terraform output`, then:

1. logs in to ECR, builds the backend and frontend images, and pushes them tagged with the git SHA;
2. registers new task-definition revisions with only the image changed;
3. runs the database migration and seed as a one-off ECS task and checks its exit code;
4. rolls both services and waits until they are stable;
5. smoke-tests `https://<cloudfront>/readyz`.

### Step 6: check the deployment

Open the `app_url` output:

- the token screen accepts your `APP_ACCESS_TOKEN`;
- run the main sample query: the timeline should stream (WebSocket through CloudFront and the ALB);
- export a PDF (Gotenberg sidecar);
- the system card shows the LLM chain (OpenAI → Gemini if keys are set) and tracing status;
- the demo controls card says the toggles are disabled on this deployment.

Logs (same `AWS_PROFILE`): `aws logs tail /ecs/policy-analytics/api --follow` (also `/gotenberg` and `/web`).

### Step 7: deploy through the pipeline (GitHub Actions + OIDC)

`.github/workflows/deploy-ecs.yml` runs the same script in CI, authenticating with GitHub OIDC, so no
AWS keys are stored in GitHub. In the repository settings:

1. **Environments → New environment `aws`.** Under *Deployment branches and tags*, allow `main` and
   tags matching `v*`. The IAM role trusts exactly this environment
   (`repo:<owner>/<repo>:environment:aws`).
2. **Secrets and variables → Actions → Secrets:** `AWS_DEPLOY_ROLE_ARN` =
   `terraform output -raw github_deploy_role_arn`.
3. **Variables:** set each from `terraform output`:

   | Variable | Output |
   |---|---|
   | `ECR_BACKEND` | `ecr_backend` |
   | `ECR_FRONTEND` | `ecr_frontend` |
   | `CLUSTER` | `cluster` |
   | `API_SERVICE` | `api_service` |
   | `WEB_SERVICE` | `web_service` |
   | `SUBNETS` | `subnets` |
   | `TASKS_SG` | `tasks_security_group` |
   | `APP_URL` | `app_url` |

4. Run it: **Actions → Deploy to AWS ECS → Run workflow**, or push a tag (`git tag v1.0.0 && git push
   origin v1.0.0`).

**`Not authorized to perform sts:AssumeRoleWithWebIdentity`:** the token's subject doesn't match the
role's trust policy. Find what GitHub actually sent in CloudTrail:

```bash
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
  --max-results 3 --query "Events[].CloudTrailEvent" --output text | grep -o '"userName":"[^"]*"'
```

If it looks like `repo:<owner>@<number>/<repo>@<number>:environment:aws`, your repo uses GitHub's
immutable-ID subject format. Put the two numbers in `terraform.tfvars` as `github_owner_id` and
`github_repo_id`, then run `make aws-plan` and `make aws-apply` (one in-place change to the role). If the
environment part differs (e.g. `environment:AWS`), rename the GitHub environment to exactly `aws`.

**Rollback:** ECS's deployment circuit breaker rolls back a deployment whose tasks fail health checks.
To return to an earlier version, re-run the workflow on that commit, or point the service at an older
task-definition revision (`aws ecs update-service --task-definition policy-analytics-api:<revision>`).

### Step 8: pause between sessions, destroy at the end

Git Bash on Windows, Terminal on macOS. `aws-pause` and `aws-resume` fail from PowerShell or cmd
(*"The system cannot find the file specified"*), because they need `bash`.

```bash
export AWS_PROFILE=<your-sso-profile>   # if this is a new shell
make aws-pause       # services to 0 tasks, RDS stopped: about US$1/day (ALB + storage)
make aws-resume      # start RDS, wait, scale services back to 1 (about 10 minutes)
make aws-destroy     # delete everything (ECR images and secrets included)
```

AWS restarts a stopped RDS instance automatically after 7 days, so pause again or destroy after the
evaluation.

## 4. Langfuse

Optional and off unless keys are set. Create a project on Langfuse Cloud (Hobby tier: 50k units a
month), copy the public and secret keys, and set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and
`LANGFUSE_BASE_URL` (or `LANGFUSE_HOST`) for your region: `https://cloud.langfuse.com` (EU) or
`https://us.cloud.langfuse.com` (US). Each analysis becomes one trace, with nested LLM and tool spans,
fallback metadata, verifier scores, and masking of keys, emails and NRIC-like ids. Keep it off for load
tests (`docker-compose.loadtest.yml` does this) to protect the quota. For government use, self-hosting
Langfuse keeps traces inside the deployment boundary; only the host variable changes.

## 5. Alternative: Google Cloud Run (`asia-southeast1`)

Not deployed, but the same images run there:

| AWS | Cloud Run equivalent |
|---|---|
| ECR | Artifact Registry |
| ECS api service + Gotenberg sidecar | Cloud Run service with a sidecar container |
| ALB path routing | Frontend service whose nginx proxies `/api` and `/ws` to the api URL (`API_UPSTREAM`) |
| RDS | Cloud SQL for PostgreSQL via the Cloud SQL connector (`DB_HOST`/`DB_USER`/`DB_PASSWORD`) |
| Secrets Manager | Secret Manager mounted as env vars |
| GitHub OIDC role | Workload Identity Federation |
| One-off migration task | Cloud Run Job running `python -m app.db.init` |

Cloud Run specifics: use instance-based billing (CPU always allocated) so background analyses keep
running after the POST returns; `min-instances = max-instances = 1` for the single-replica runner; and
session affinity for WebSockets. Client reconnect with event replay covers dropped sockets.

## 6. Scaling out

1. Move the runner to an **arq worker on Redis** and the event bus to **Redis pub/sub**; both sit behind
   small interfaces (`TaskRunner.start/resume/cancel`, `event_bus.publish/subscribe`).
2. Swap `MemorySaver` for LangGraph's **Postgres checkpointer**, so a clarification survives a restart
   and any replica can resume it.
3. Then scale the api service horizontally behind the ALB and run workers as their own service.
4. For production: tasks in private subnets with VPC endpoints or a NAT gateway, WAF on CloudFront,
   SSO in front of the app instead of a shared token, and an S3 backend with locking for Terraform
   state.
