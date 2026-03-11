# cgpt — AI CLI

A single-file terminal CLI supporting **OpenAI** and **Claude (Anthropic)** with project-based personas, persistent conversation history, semantic caching, and rich markdown output.

Invoked as `??` after install.

## Requirements

- Python 3.10+
- OpenAI API key and/or Anthropic API key

## Install

```bash
zsh install.sh
source ~/.zshrc
```

Set your API keys:

```bash
nano ~/.config/chatgpt-cli/config.yaml
```

## Usage

```bash
?? what is the difference between CMD and ENTRYPOINT

# DevOps / Cloud
?? devops force new ECS deployment without downtime
?? monitoring write a PromQL alert for ECS task restart rate
?? pipeline bitbucket-pipelines.yml for ECS blue/green with CodeDeploy
?? security least-privilege IAM policy for ECS task reading SSM + S3

# Backend
?? python FastAPI endpoint with JWT auth and Pydantic v2 request model
?? nodejs NestJS CRUD service with Prisma and PostgreSQL
?? sql Aurora PostgreSQL autovacuum not running on large table — diagnose

# Frontend
?? reactjs login form with react-hook-form, zod, and TanStack Query mutation
?? frontend responsive card grid with CSS Grid, dark mode, hover animations

# Review
?? review              # then paste Dockerfile / Terraform / IAM policy / code
cat file.py | ?? review check this for security issues
```

## Projects

| Project | Focus |
|---------|-------|
| `devops` | AWS — ECS Fargate, EKS, Aurora, ElastiCache Valkey, CloudFront, Cognito, Lambda@Edge |
| `python` | FastAPI, Pydantic v2, SQLAlchemy async, boto3, Lambda, aws-lambda-powertools |
| `nodejs` | NestJS / Express, TypeScript strict, Prisma, Zod, REST / GraphQL, Jest |
| `reactjs` | React 18, TypeScript, TanStack Query, Tailwind + shadcn/ui, react-hook-form + zod |
| `frontend` | HTML5 semantic, CSS3 (Grid/Flexbox/custom properties), vanilla JS, WCAG 2.1 AA |
| `sql` | Aurora MySQL 8 / PG 15/16, ElastiCache Valkey, RDS Proxy, PgBouncer |
| `monitoring` | Prometheus, Thanos, Grafana, Alertmanager, CloudWatch |
| `pipeline` | Bitbucket Pipelines, Jenkins, OIDC role assumption, ECS/EKS deployments |
| `review` | Code review — security, IaC, Dockerfiles, Python, SOC2 gap detection |
| `security` | IAM, KMS, GuardDuty, Security Hub, SOC2 CC6/CC7/CC8 |
| `??` | General — stack-aware default |

## Provider Selection

Provider is resolved in priority order: **project YAML** → **`-P` flag** → **`defaults.provider` in config**.

```bash
?? --status              # show active provider, model, API key status
?? --set claude          # permanently switch default to Claude
?? --set openai          # permanently switch default to OpenAI
?? -P claude <question>  # use Claude for this query only
?? -P openai <question>  # use OpenAI for this query only
```

Per-project provider override (`~/.config/chatgpt-cli/projects/myproject.yaml`):
```yaml
provider: claude
model: claude-sonnet-4-6
```

## Flags

```bash
# Conversations
??p                             # list all projects + history + cache counts
??h                             # show conversation history (current project)
??c                             # clear history (current project)
?? -p <project> <question>      # explicit project flag
?? -n <project> <question>      # ignore history for this turn only
?? --history-search KEYWORD     # search history across all projects
?? --copy                       # copy last answer to clipboard

# Provider
?? --status                     # provider / model / API key overview
?? --set claude                  # set default provider (persisted to config)
?? -P claude <question>          # override provider for one query

# Cache
?? --cache-stats                 # hit/miss stats per project
?? --cache-search KEYWORD        # search cached questions
?? --clear-cache                 # clear all cache (or -p for one project)
?? --cache-delete "question"     # delete one matching cache entry
?? --cache-backup cache.json     # backup all cache to file
?? --cache-restore cache.json    # restore cache from file
?? -C <question>                 # bypass cache for this query

# Usage & setup
?? --usage                       # token usage + cost report (by provider, project, model)
?? --no-stream <question>        # disable streaming
?? --init                        # set up config and project files
```

## Configuration

Runtime config at `~/.config/chatgpt-cli/config.yaml`:

```yaml
openai:
  api_key: "sk-..."             # pragma: allowlist secret
  model: "gpt-4o"
  max_tokens: 2048
  temperature: 0.7

anthropic:
  api_key: "sk-ant-..."         # pragma: allowlist secret
  model: "claude-sonnet-4-6"   # claude-opus-4-6 | claude-sonnet-4-6 | claude-haiku-4-5-20251001
  max_tokens: 2048
  temperature: 0.7

defaults:
  provider: "openai"            # openai | claude
  project: "default"
  history_limit: 20
  stream: true

display:
  markdown: true
  show_project_header: true
  show_timestamp: true

cache:
  enabled: true
  ttl_days: 7
  max_entries: 200
  similarity_threshold: 0.82
```

## Custom Projects

Add a YAML file to `~/.config/chatgpt-cli/projects/`:

```yaml
# ~/.config/chatgpt-cli/projects/terraform.yaml
description: "Terraform IaC — AWS modules, state, workspaces"
provider: claude                  # optional: openai | claude
model: claude-sonnet-4-6          # optional: override model
temperature: 0.2                  # optional: override temperature
system_prompt: |
  You are a Terraform expert focused on AWS...
```

Then use immediately: `?? terraform refactor VPC module for multi-AZ`

## File Layout

```
~/.config/chatgpt-cli/
├── config.yaml          # API keys, model settings  (chmod 600)
├── projects/            # System prompts per persona
├── history/             # Persistent conversation per project
└── cache/               # Semantic response cache per project
```

## Security Scanning

Pre-commit hooks run on every commit and push:

- **gitleaks** — hardcoded secrets and API keys
- **detect-secrets** — entropy-based detection
- **semgrep** — secrets patterns + Python security rules

Setup:

```bash
pip install pre-commit detect-secrets
brew install gitleaks semgrep
pre-commit install --hook-type pre-commit --hook-type pre-push
```
