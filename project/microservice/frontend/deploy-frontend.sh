#!/usr/bin/env bash
# deploy-frontend.sh — Deploy frontend to S3 static website hosting
# Usage: ./frontend/deploy-frontend.sh
set -euo pipefail

# ── CONFIG — edit these ───────────────────────────────────────────────────────
BUCKET_NAME="your-microservice-frontend"
AWS_REGION="us-east-1"
# ─────────────────────────────────────────────────────────────────────────────

FRONTEND_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "▶ Creating S3 bucket (skip if already exists)..."
aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$AWS_REGION" \
  $([ "$AWS_REGION" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=$AWS_REGION") \
  2>/dev/null || echo "   Bucket already exists, continuing..."

echo "▶ Disabling block public access..."
aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

echo "▶ Applying bucket policy..."
sed "s/YOUR_BUCKET_NAME/$BUCKET_NAME/g" "$FRONTEND_DIR/s3-bucket-policy.json" > /tmp/policy.json
aws s3api put-bucket-policy --bucket "$BUCKET_NAME" --policy file:///tmp/policy.json

echo "▶ Enabling static website hosting..."
aws s3 website "s3://$BUCKET_NAME" \
  --index-document index.html \
  --error-document index.html

echo "▶ Uploading frontend files..."
aws s3 sync "$FRONTEND_DIR" "s3://$BUCKET_NAME" \
  --exclude "*.sh" \
  --exclude "*.json" \
  --exclude ".DS_Store" \
  --cache-control "no-cache" \
  --delete

echo ""
echo "✅ Frontend deployed!"
echo "   URL: http://${BUCKET_NAME}.s3-website-${AWS_REGION}.amazonaws.com"
echo ""
echo "   Next: Enter your ECS EC2 ALB or public IP as the API Base URL in the dashboard."
