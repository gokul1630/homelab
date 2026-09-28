terraform {
  required_version = ">= 1.6.0"
  backend "s3" {
    region                      = "ap-south-1"
    bucket                      = "state-backend-ebdae16"
    key                         = "devops-ecs-ecr-github-actions/dev/terraform.tfstate"
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

module "networking" {
  source   = "../../modules/networking"
  name     = var.project_name
  vpc_cidr = var.vpc_cidr
}

module "ecr" {
  source = "../../modules/ecr"
  name   = var.project_name
}

module "security" {
  source         = "../../modules/security"
  name           = var.project_name
  vpc_id         = module.networking.vpc_id
  container_port = var.container_port
}

module "iam" {
  source             = "../../modules/iam"
  name               = var.project_name
  github_repository  = var.github_repository
  ecr_repository_arn = module.ecr.repository_arn
}

module "ecs" {
  source             = "../../modules/ecs"
  name               = var.project_name
  aws_region         = var.aws_region
  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  alb_sg_id          = module.security.alb_sg_id
  ecs_sg_id          = module.security.ecs_sg_id
  container_port     = var.container_port
  ecr_repository_url = module.ecr.repository_url
  execution_role_arn = module.iam.ecs_execution_role_arn
  desired_count      = var.desired_count
  min_capacity       = var.min_capacity
  max_capacity       = var.max_capacity
  enable_autoscaling = false
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecs_service_name" {
  value = module.ecs.service_name
}

output "alb_dns_name" {
  value = module.ecs.alb_dns_name
}

output "github_actions_role_arn" {
  value = module.iam.github_actions_role_arn
}
