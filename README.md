# cgpt — ChatGPT CLI

A single-file terminal CLI for ChatGPT with project-based personas, persistent conversation history, and rich markdown output.

Invoked as `??` after install.

## Requirements

- Python 3.10+
- OpenAI API key

## Install

```bash
zsh install.sh
source ~/.zshrc
```

Sets your API key:

```bash
nano ~/.config/chatgpt-cli/config.yaml
```

## Usage

```bash
?? what is the difference between CMD and ENTRYPOINT

?? devops force new ECS deployment without downtime
?? monitoring write a PromQL alert for ECS task restart rate
?? pipeline bitbucket-pipelines.yml for ECS blue/green with CodeDeploy
?? python boto3 script to rotate ElastiCache auth tokens
?? sql Aurora PostgreSQL autovacuum not running on large table — diagnose
?? review              # then paste Dockerfile / Terraform / IAM policy
?? security least-privilege IAM policy for ECS task reading SSM + S3
```

## Projects

| Command | Persona |
|---------|---------|
| `?? devops` | AWS — ECS Fargate, EKS, Aurora, ElastiCache Valkey, CloudFront OAC, Cognito, Lambda@Edge |
| `?? monitoring` | Prometheus, Thanos, Grafana, Alertmanager, CloudWatch |
| `?? pipeline` | Bitbucket Pipelines, Jenkins, OIDC role assumption, Playwright/Locust gates, SOC2 controls |
| `?? python` | Python 3.10/3.11, boto3, aws-lambda-powertools, aioboto3 |
| `?? sql` | Aurora MySQL 8 / PG 15/16, ElastiCache Valkey, RDS Proxy, PgBouncer |
| `?? review` | 7-dimension code review with severity levels, healthcare data flag, SOC2 gap detection |
| `?? security` | SOC2 CC6/CC7/CC8, KMS, GuardDuty, Security Hub, healthcare PII |
| `??` | General — stack-aware default |

## Flags

```bash
??p                        # list all projects + history turn count
??h                        # show conversation history (current project)
??c                        # clear history (current project)
?? -p devops <question>    # explicit project flag
?? -n devops <question>    # ignore history for this turn only
?? --no-stream <question>  # disable streaming
```

## Configuration

Runtime config at `~/.config/chatgpt-cli/config.yaml` (created on first install):

```yaml
openai:
  api_key: "sk-..." # pragma: allowlist secret
  model: "gpt-4o"
  max_tokens: 2048
  temperature: 0.7

defaults:
  project: "default"
  history_limit: 20   # messages kept per project (each turn = 2)
  stream: true

display:
  markdown: true
  show_project_header: true
  show_timestamp: true
```

## Custom Projects

Add a YAML file to `~/.config/chatgpt-cli/projects/`:

```yaml
# ~/.config/chatgpt-cli/projects/terraform.yaml
description: "Terraform IaC — AWS modules, state, workspaces"
system_prompt: |
  You are a Terraform expert focused on AWS...
```

Then use it immediately: `?? terraform refactor VPC module for multi-AZ`

## File Layout

```
~/.config/chatgpt-cli/
├── config.yaml          # API key, model settings  (chmod 600)
├── projects/            # System prompts per persona
└── history/             # Persistent conversation per project
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
