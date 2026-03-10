# ChatGPT CLI — Projects Skillset Reference

**Stack:** Tin Tran / DevOps Engineer / Talosix / Ho Chi Minh City
**Updated:** 2025

---

## Projects Overview

| Alias | Project File | Best For |
|---|---|---|
| `??` | `default.yaml` | General questions, stack-aware context |
| `?? devops` | `devops.yaml` | AWS services, ECS, EKS, Aurora, CloudFront, Cognito |
| `?? monitoring` | `monitoring.yaml` | Prometheus, Grafana, Thanos, Alertmanager, CloudWatch |
| `?? pipeline` | `pipeline.yaml` | Bitbucket Pipelines, Jenkins, ECS/EKS deployments |
| `?? python` | `python.yaml` | boto3, Lambda, automation scripts, CLI tools |
| `?? sql` | `sql.yaml` | Aurora MySQL/PostgreSQL, ElastiCache Redis/Valkey |
| `?? review` | `review.yaml` | Code review, IaC, Dockerfiles, security audit |
| `?? security` | `security.yaml` | IAM, SOC2, Secrets, GuardDuty, DevSecOps |

---

## `devops` — AWS Infrastructure

**Scope:** Day-to-day AWS console and CLI operations

```bash
# ECS Fargate
?? devops force new deployment without downtime on ECS service auth-service
?? devops ECS task is stuck in PENDING state — how do I diagnose
?? devops configure ECS Service Connect between two Fargate services
?? devops set up CloudFront OAC for private S3 bucket
?? devops Cognito JWT validation in Lambda@Edge — full implementation
?? devops ElastiCache Valkey vs Redis — what changed and migration path
?? devops Aurora PostgreSQL upgrade from 14 to 16 with minimal downtime
?? devops right-size Fargate task CPU/memory based on CloudWatch metrics
```

**Key services:** ECS Fargate, EKS, Aurora MySQL/PostgreSQL, ElastiCache Redis/Valkey,
S3, CloudFront, Cognito, Lambda@Edge, VPC, ALB/NLB, Terraform, CDK

---

## `monitoring` — Observability Stack

**Scope:** Metrics, dashboards, alerts, long-term storage

```bash
# PromQL
?? monitoring write a PromQL alert for ECS task restart rate > 3 in 5 minutes
?? monitoring Aurora connection exhaustion alert with Thanos ruler
?? monitoring Grafana dashboard for ECS Fargate service health — panel JSON
?? monitoring Alertmanager route config to send critical to PagerDuty, warning to Slack
?? monitoring Thanos sidecar vs Thanos receive — which for Fargate-based Prometheus
?? monitoring CloudWatch Log Insights query for 5xx errors grouped by path
?? monitoring ElastiCache Redis eviction rate alert in Prometheus
```

**Key tools:** Prometheus, Grafana, Thanos (sidecar/querier/store/compactor),
Alertmanager, CloudWatch Metrics/Logs/Alarms/Container Insights

---

## `pipeline` — CI/CD

**Scope:** Build, test, deploy pipelines for ECS/EKS workloads

```bash
# Bitbucket + Jenkins
?? pipeline bitbucket-pipelines.yml for ECS blue/green deployment with CodeDeploy
?? pipeline Jenkins shared library for multi-service ECS deployment
?? pipeline add Trivy container scan step to Bitbucket pipeline before ECR push
?? pipeline OIDC role assumption in Bitbucket Pipelines — no long-lived keys
?? pipeline Playwright E2E as a pipeline gate before production deployment
?? pipeline parallel Bitbucket steps for unit test + lint + security scan
?? pipeline ECS rolling deploy rollback trigger on CloudWatch alarm breach
```

**Key tools:** Bitbucket Pipelines, Jenkins (Declarative/Scripted),
Docker, ECR, CodeDeploy, Terraform/CDK in pipelines, Playwright, Locust

---

## `python` — Scripting & Lambda

**Scope:** boto3 automation, Lambda functions, DevOps CLI tools

```bash
# Python automation
?? python boto3 script to rotate ElastiCache auth tokens across all clusters
?? python Lambda function with powertools to process SQS events with DLQ handling
?? python async boto3 script to snapshot all Aurora clusters across regions
?? python ECS service deployment tracker — poll until stable or timeout
?? python Cognito user pool migration Lambda trigger with error handling
?? python S3 presigned URL generator with CloudFront signed cookies alternative
?? python list all Fargate tasks with CPU/memory utilization above threshold
```

**Key libs:** boto3, aws-lambda-powertools, typer, rich, pydantic, httpx, aioboto3
**Runtime:** Python 3.10/3.11 (conda), Lambda Python 3.11

---

## `sql` — Databases

**Scope:** Aurora queries, performance, Redis/Valkey patterns

```bash
# Aurora + Redis
?? sql find slow queries on Aurora PostgreSQL and add missing indexes
?? sql Aurora MySQL max_connections formula for Fargate + RDS Proxy setup
?? sql Aurora PostgreSQL autovacuum not running on large table — diagnose
?? sql ElastiCache Redis cluster mode key distribution and hotspot detection
?? sql Aurora failover testing — promote reader without data loss
?? sql Redis SCAN vs KEYS — safe production pattern for key enumeration
?? sql Aurora PostgreSQL EXPLAIN ANALYZE output — what to look for
```

**Databases:** Aurora MySQL 8.0, Aurora PostgreSQL 15/16, ElastiCache Redis 7, Valkey 7
**Tools:** RDS Proxy, PgBouncer, Performance Insights, Enhanced Monitoring

---

## `review` — Code & Config Review

**Scope:** Review IaC, pipelines, Dockerfiles, Python, configs

```bash
# Paste code after the command
?? review                 # then paste Dockerfile
?? review                 # then paste Terraform module
?? review                 # then paste bitbucket-pipelines.yml
?? review                 # then paste IAM policy JSON
?? review                 # then paste Prometheus alerting rule
```

**Severity levels returned:**
- 🔴 **Critical** — Security vulnerability, data loss risk, compliance violation
- 🟡 **Warning** — Performance issue, reliability gap, bad practice
- 🔵 **Suggestion** — Readability, maintainability, cost optimization

---

## `security` — DevSecOps

**Scope:** IAM, SOC2, secrets, network security, compliance

```bash
# Security & compliance
?? security least-privilege IAM policy for ECS task running Node.js that reads SSM + S3
?? security SOC2 CC6.1 controls for ECS Fargate workloads — checklist
?? security audit all IAM roles with S3:* wildcard using CLI
?? security secrets rotation pattern — Secrets Manager + ECS Fargate without restart
?? security GuardDuty finding EC2 credential exfiltration — response runbook
?? security CloudFront + S3 OAC policy — deny all direct S3 access
?? security Cognito PKCE flow with Lambda@Edge JWT validation — secure pattern
```

**Controls:** SOC2 Type II (CC6/CC7/CC8), KMS, GuardDuty, Security Hub,
CloudTrail, VPC Flow Logs, ECR scanning, IAM Access Analyzer

---

## History & Session Management

```bash
# History commands
??p                         # list all projects + turn count
?? -p devops --history      # show devops conversation history
?? -p devops --clear        # clear devops history (start fresh topic)
?? -n devops <question>     # one-off question, ignore history this turn

# Add a new project
nano ~/.config/chatgpt-cli/projects/terraform.yaml
```

---

## Adding Custom Projects

```yaml
# ~/.config/chatgpt-cli/projects/terraform.yaml
description: "Terraform IaC — AWS modules, state, workspaces"
system_prompt: |
  You are a Terraform expert focused on AWS. Provide HCL with:
  - Variable definitions and validation blocks
  - Module structure for multi-account AWS (dev/staging/prod)
  - Remote state (S3 + DynamoDB locking)
  - Terragrunt patterns where relevant
  Tin uses Terraform with CDK. Assume AWS provider ~5.x.
```

```bash
# Then immediately use it
?? terraform refactor VPC module to support multiple AZs with variable count
```

---

## Config Location

```
~/.config/chatgpt-cli/
├── config.yaml          # API key, model, defaults  ← chmod 600
├── projects/            # Project system prompts
│   ├── default.yaml
│   ├── devops.yaml
│   ├── monitoring.yaml
│   ├── pipeline.yaml
│   ├── python.yaml
│   ├── sql.yaml
│   ├── review.yaml
│   └── security.yaml
└── history/             # Persistent conversation per project
    ├── devops.json
    └── monitoring.json
```
