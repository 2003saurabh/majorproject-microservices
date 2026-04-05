# 🚀 Complete Manual: Deploying Microservices on Amazon EKS

---

## 📌 Overview

This manual explains how to deploy a multi-service FastAPI-based microservices application on Kubernetes using Amazon EKS.

### Architecture Components
- Items Service (FastAPI)
- Auth Service (FastAPI)
- Orders Service (FastAPI)
- PostgreSQL (StatefulSet)
- Kubernetes Services (ClusterIP)
- Ingress (AWS ALB)
- Docker + ECR

---

## 📁 Project Structure

```
project/
├── auth_service/
├── microservice/ (items)
├── orders_service/
├── k8s/
│   ├── app/
│   ├── auth/
│   ├── orders/
│   ├── postgres/
│   ├── ingress.yml
│   └── namespace.yml
```

---

## ⚙️ Prerequisites

- AWS Account
- EKS Cluster (2 nodes)
- kubectl configured
- eksctl installed
- Docker installed
- Helm installed

---

## 🐳 Step 1: Build Docker Images

```
docker build -t items ./microservice
docker build -t auth ./auth_service
docker build -t orders ./orders_service
```

---

## 📦 Step 2: Push Images to ECR

### Login to ECR
```
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-south-1.amazonaws.com
```

### Tag Images
```
docker tag items <ECR>/items:latest
docker tag auth <ECR>/auth:latest
docker tag orders <ECR>/orders:latest
```

### Push Images
```
docker push <ECR>/items:latest
docker push <ECR>/auth:latest
docker push <ECR>/orders:latest
```

---

## ☸️ Step 3: Kubernetes Setup

### Create Namespace
```
kubectl apply -f k8s/namespace.yml
```

---

## 🗄️ Step 4: Deploy PostgreSQL

```
kubectl apply -f k8s/postgres/
```

---

## 🔐 Step 5: Create Secrets & ConfigMaps

```
kubectl apply -f k8s/secret.yml
kubectl apply -f k8s/auth/secret.yml
kubectl apply -f k8s/orders/secret.yml
```

---

## 🚀 Step 6: Deploy Services

```
kubectl apply -f k8s/app/
kubectl apply -f k8s/auth/
kubectl apply -f k8s/orders/
```

---

## 🌐 Step 7: Install AWS Load Balancer Controller

### Associate OIDC
```
eksctl utils associate-iam-oidc-provider --region ap-south-1 --cluster <cluster-name> --approve
```

### Create IAM Policy
```
curl -O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json
aws iam create-policy --policy-name AWSLoadBalancerControllerIAMPolicy --policy-document file://iam_policy.json
```

### Create Service Account
```
eksctl create iamserviceaccount \
  --cluster <cluster-name> \
  --namespace kube-system \
  --name aws-load-balancer-controller \
  --attach-policy-arn arn:aws:iam::<account-id>:policy/AWSLoadBalancerControllerIAMPolicy \
  --approve
```

### Install Controller
```
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=<cluster-name> \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

---

## 🌍 Step 8: Apply Ingress

```
kubectl apply -f k8s/ingress.yml
```

Check:
```
kubectl get ingress -n microservices-dev
```

---

## 🔧 Important Configuration

### FastAPI root_path
Each service must include:

```
app = FastAPI(root_path="/items")
app = FastAPI(root_path="/auth")
app = FastAPI(root_path="/orders")
```

---

## 🧪 Verification

### Check Pods
```
kubectl get pods -n microservices-dev
```

### Check Services
```
kubectl get svc -n microservices-dev
```

### Test URLs
```
http://<ALB>/items/docs
http://<ALB>/auth/docs
http://<ALB>/orders/docs
```

---

## 🛠️ Troubleshooting Guide

### 404 Error
- Path mismatch
- Check ingress paths

### 503 Error
- No endpoints
- Check labels and selectors

### No ALB Created
- ALB controller not installed
- Subnets not tagged

### Image Not Updating
- Using latest tag
- Run rollout restart

---

## 🔁 Updating Application

```
docker build
docker push
kubectl rollout restart deployment <service>
```

---

## 🔐 Best Practices

- Use versioned image tags
- Enable HTTPS using ACM
- Use domain names
- Add monitoring (Prometheus/Grafana)
- Enable autoscaling (HPA)

---

## 🎯 Conclusion

You now have a fully functional microservices system deployed on EKS with ALB ingress, scalable architecture, and production-ready setup.

---

## 📥 Export Options

You can copy this file as:
- `.md` (Markdown)
- `.docx` (Word)

---

🚀 End of Manual

