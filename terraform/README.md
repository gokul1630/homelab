# End-to-End DevOps Project: GitHub Actions → ECR → ECS Fargate

A production-style DevOps portfolio project that takes a containerized application from GitHub source code to AWS ECS Fargate using GitHub Actions and Terraform.

## Resume value

This is intentionally one deep project rather than several shallow projects. It demonstrates:

- CI/CD with GitHub Actions
- Automated tests as a deployment gate
- Docker image build and versioning with Git commit SHA
- Amazon ECR with image scanning and lifecycle cleanup
- GitHub OIDC → AWS IAM temporary credentials
- Terraform modules and separate dev/prod environments
- Terraform remote state in versioned, encrypted S3
- ECS Fargate rolling deployments
- Deployment failure rollback to the previous ECS task definition
- Application Load Balancer and target health checks
- VPC networking and security groups
- CloudWatch Logs and ECS Container Insights
- ECS CPU target-tracking autoscaling

## Architecture

```text
Developer
   |
   | git push main
   v
+-----------------------+
| GitHub Repository      |
+-----------+-----------+
            |
            v
+-----------------------+
| GitHub Actions         |
| 1. Checkout            |
| 2. npm test            |
| 3. Docker build        |
| 4. Push image to ECR   |
| 5. Register task def   |
| 6. Deploy ECS          |
| 7. Wait for health     |
| 8. Rollback on failure |
+-----------+-----------+
            |
            | OIDC / temporary credentials
            v
+-----------------------+       +-----------------------+
| Amazon ECR            |       | Terraform             |
| image:<git-sha>       |       | dev / prod            |
+-----------+-----------+       | reusable modules      |
            |                   +-----------+-----------+
            v                               |
+-----------------------+                   |
| ECS Fargate Service   |<------------------+
| 2 tasks, autoscaling  |
+-----------+-----------+
            |
            v
+-----------------------+
| Application Load      |
| Balancer :80          |
+-----------+-----------+
            |
            v
+-----------------------+
| Node.js app :3000     |
| /health               |
+-----------------------+
            |
            v
       CloudWatch Logs
```

## Repository structure

```text
.
├── .github/workflows/deploy.yml
├── app/
│   ├── Dockerfile
│   ├── package.json
│   ├── server.js
│   └── server.test.js
├── bootstrap/
│   ├── main.tf
│   ├── variables.tf
│   └── terraform.tfvars.example
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars.example
│   └── prod/
│       ├── main.tf
│       ├── variables.tf
│       └── terraform.tfvars.example
├── modules/
│   ├── networking/
│   ├── security/
│   ├── ecr/
│   ├── iam/
│   └── ecs/
└── README.md
```

## Why these technologies were chosen

### GitHub Actions

The source is already in GitHub, so GitHub Actions keeps CI/CD close to the code. It also provides a clear interview discussion around workflow triggers, job dependencies, permissions and deployment gates.

### Docker

The application is packaged as a repeatable artifact. The same image built by CI is the image deployed to ECS.

### Amazon ECR

ECR is AWS's native container registry and integrates directly with ECS. Images are tagged with the Git commit SHA rather than `latest`, making deployments traceable and reproducible.

### ECS Fargate

Fargate removes EC2 instance management. The project therefore concentrates on containers, networking, IAM, deployment, scaling and observability.

### Application Load Balancer

The ALB gives the service a realistic production entry point and demonstrates listeners, target groups and health checks.

### Terraform

Terraform makes the AWS infrastructure reproducible and reviewable. Reusable modules prevent the dev and prod configurations from becoming two independent copies of the same infrastructure.

### S3 remote state

Terraform state is stored remotely in an encrypted, versioned S3 bucket. This prevents the important state file from being tied to one developer's laptop and allows the infrastructure workflow to be shared.

The state bucket is bootstrapped separately because Terraform cannot use a backend bucket that it is simultaneously trying to create.

### Separate dev and prod environments

The same modules are reused with environment-specific configuration. This demonstrates environment isolation without duplicating all infrastructure code.

### OIDC

GitHub Actions does not store a permanent AWS access key. GitHub issues an OIDC token and AWS STS exchanges it for temporary credentials after validating the repository and branch condition.

This is safer than storing long-lived `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` credentials in GitHub.

## CI/CD flow

### 1. Push code

```text
git push origin main
```

Triggers the workflow.

### 2. Checkout

GitHub Actions checks out the exact commit.

### 3. Test

```bash
npm install
npm test
```

If tests fail, the deployment job is blocked with `needs: test`.

### 4. Authenticate to AWS

GitHub uses OIDC to assume the IAM role created by Terraform.

### 5. Build

```bash
docker build -t <ECR>/<repo>:<git-sha> ./app
```

### 6. Push

The image is pushed to ECR.

Example:

```text
123456789012.dkr.ecr.ap-south-1.amazonaws.com/devops-ecs-demo-prod:8f4a2c...
```

### 7. Update ECS task definition

The workflow copies the current task definition, replaces only the container image and registers a new ECS task definition revision.

### 8. Deploy

ECS performs a rolling deployment and GitHub Actions waits for service stability.

### 9. Rollback

Before deployment, the workflow records the current task definition ARN. If the deployment fails, the workflow updates the ECS service back to that previous revision and waits for stability.

This gives you a concrete interview demonstration of failed deployment recovery.

## Terraform design

### Bootstrap

`bootstrap/` creates only the Terraform state bucket.

Run it once:

```bash
cd bootstrap
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init
terraform apply
```

Copy the resulting bucket name into both environment `main.tf` backend blocks, replacing:

```text
REPLACE_TF_STATE_BUCKET
```

Do not commit `terraform.tfvars`.

### Environments

Each environment calls the same modules:

```text
modules/networking
modules/security
modules/ecr
modules/iam
modules/ecs
```

Initialize and apply dev:

```bash
cd environments/dev
cp terraform.tfvars.example terraform.tfvars
# set github_repository = "your-org/your-repo"
terraform init
terraform plan
terraform apply
```

Apply prod similarly:

```bash
cd environments/prod
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## First-time ECS bootstrap

There is one practical bootstrap dependency: the ECS task definition initially references an ECR image called `bootstrap`. ECR must exist before an image can be pushed.

Use this one-time sequence:

```bash
# 1. Create ECR/IAM/networking/ECS infrastructure
cd environments/prod
terraform apply -target=module.ecr -target=module.iam -target=module.networking -target=module.security

# 2. Build and push a bootstrap image
REGION=ap-south-1
REPO=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REPO

docker build -t "$REPO:bootstrap" ../../app
docker push "$REPO:bootstrap"

# 3. Create the complete ECS service
terraform apply
```

After that, normal development is simply:

```text
git push → GitHub Actions → test → build → ECR → ECS
```

## GitHub configuration

Create this repository secret:

```text
AWS_ROLE_ARN = <terraform output github_actions_role_arn>
```

The workflow requires:

```yaml
permissions:
  id-token: write
  contents: read
```

The Terraform IAM trust policy only permits the configured GitHub repository's `main` branch to assume the role.

## Security model

The project intentionally demonstrates several security boundaries:

```text
GitHub
  |
  | OIDC token
  v
AWS IAM role
  |
  +--> ECR push permissions
  +--> ECS deployment permissions
  +--> iam:PassRole only for ECS execution role
```

The ECS security group allows application traffic only from the ALB security group.

```text
Internet → ALB :80 → ECS :3000
                    X
             direct internet access
```

## Observability

ECS sends container logs to:

```text
CloudWatch Log Group: /ecs/<project-name>
```

The ECS cluster also enables Container Insights.

The ALB checks:

```text
GET /health
```

A task must pass health checks before it can receive normal traffic.

## Autoscaling

The ECS service starts with two tasks and can scale from two to four tasks based on:

```text
ECSServiceAverageCPUUtilization
```

Target:

```text
60% CPU
```

This demonstrates service-level autoscaling rather than manually adding EC2 instances.

## Failure scenarios to demonstrate in an interview

### Test failure

Break the test intentionally.

Expected result:

```text
test fails → build/deploy job does not run
```

### Application deployment failure

Push an image that makes `/health` fail.

Expected result:

```text
new task unhealthy
       ↓
ECS deployment does not stabilize
       ↓
GitHub Actions fails
       ↓
previous task definition restored
```

### Container crash

Make the application exit unexpectedly.

Expected result:

```text
ECS detects stopped task
       ↓
service replaces task
```

### CPU load

Generate application traffic and observe ECS CPU scaling.

### Terraform change

Modify a resource and run:

```bash
terraform plan
```

Explain what Terraform wants to change before applying it.

## Interview questions you should be able to answer

1. Why ECS instead of EC2?
2. Why Fargate?
3. How does GitHub authenticate to AWS without access keys?
4. What happens after a Git push?
5. Why use the Git SHA as the Docker tag?
6. How does ECS receive the new image?
7. How does the ALB route traffic to ECS tasks?
8. What is a target group?
9. What happens when a task becomes unhealthy?
10. How does ECS autoscaling work?
11. What happens if a deployment fails?
12. How does the rollback work?
13. Why Terraform?
14. Why use modules?
15. Why separate dev and prod?
16. Why use remote Terraform state?
17. Why version the state bucket?
18. What is the ECS execution role?
19. What is `iam:PassRole` and why is it needed?
20. How would you store application secrets?
21. How would you make ECS tasks private instead of public?
22. How would you add HTTPS?
23. How would you implement blue/green deployment?
24. How would you monitor application errors?
25. How would you reduce AWS cost?

## Production improvements you can discuss

This project is intentionally achievable as a portfolio project. In a real production environment, discuss these next steps:

- Private ECS subnets with NAT Gateway or VPC endpoints
- HTTPS with ACM and an HTTPS ALB listener
- AWS Secrets Manager or SSM Parameter Store
- WAF in front of the ALB
- Blue/green deployments with CodeDeploy
- CloudWatch alarms and SNS notifications
- Centralized dashboards
- Terraform CI with `fmt`, `validate`, `plan` and approval before apply
- Separate AWS accounts for dev/staging/prod
- Dependency pinning and lock files
- Container image signing and stronger supply-chain controls

## Resume description

**AWS ECS DevOps Deployment Platform**

Built an end-to-end containerized CI/CD platform using Terraform, GitHub Actions, Docker, Amazon ECR and ECS Fargate. Implemented automated testing, commit-SHA image versioning, ECR publishing, OIDC-based AWS authentication, ECS rolling deployments and automatic rollback on failed health checks. Provisioned reusable Terraform modules for VPC networking, security groups, ECR, IAM, ALB, ECS, CloudWatch and CPU-based autoscaling, with separate dev/prod environments and encrypted/versioned remote Terraform state.

### Technologies

```text
AWS | ECS Fargate | ECR | ALB | VPC | IAM | OIDC |
Terraform | Docker | GitHub Actions | CloudWatch | Node.js
```

## Cost awareness

This project uses billable AWS resources. Fargate, ALB and related networking/logging resources can generate charges even when traffic is low.

For learning, create the infrastructure only when needed and destroy it afterward:

```bash
terraform destroy
```

Do not destroy shared production infrastructure blindly. Use the dev environment for experimentation.
