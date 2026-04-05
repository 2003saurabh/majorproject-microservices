#!/usr/bin/env bash
# deploy.sh — Build, push to ECR, and update ECS service (EC2 launch type)
# Usage: ./deployment/deploy.sh [image-tag]
set -euo pipefail

# ── CONFIG — edit these ───────────────────────────────────────────────────────
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="YOUR_ACCOUNT_ID"
ECR_REPO="python-microservice"
ECS_CLUSTER="your-ec2-cluster-name"
ECS_SERVICE="python-microservice-service"
IMAGE_TAG="${1:-latest}"
# ─────────────────────────────────────────────────────────────────────────────

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

echo "▶ Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "▶ Building image..."
docker build -t "${ECR_REPO}:${IMAGE_TAG}" .

echo "▶ Tagging image..."
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"

echo "▶ Pushing to ECR..."
docker push "${ECR_URI}:${IMAGE_TAG}"

echo "▶ Registering updated task definition..."
aws ecs register-task-definition \
  --cli-input-json file://deployment/ecs-task-definition.json \
  --region "$AWS_REGION"

echo "▶ Updating ECS service on EC2 cluster (force new deployment)..."
aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service "$ECS_SERVICE" \
  --force-new-deployment \
  --region "$AWS_REGION"

echo "✅ Deployment triggered. Monitor at:"
echo "   https://${AWS_REGION}.console.aws.amazon.com/ecs/v2/clusters/${ECS_CLUSTER}/services/${ECS_SERVICE}"
