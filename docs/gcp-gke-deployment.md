# GCP and GKE Deployment Preparation

This document describes the deployment preparation for the AI DevOps Kubernetes Agent, without creating any cloud resources automatically.

Important:
- Do not run the resource-creation commands below until the user explicitly approves them.
- No GCP resources are created as part of this project step.
- This project remains read-only with respect to Kubernetes.

## 1. Required GCP configuration

Set the project and region configuration before any deployment work:

```bash
export PROJECT_ID="TARGET_PROJECT_ID"
export REGION="us-central1"
export CLUSTER_NAME="ai-devops-agent"
export REPOSITORY_NAME="ai-devops-agent-repo"
export WORKLOAD_IDENTITY_SA="ai-devops-agent-sa"
export WORKLOAD_IDENTITY_EMAIL="${WORKLOAD_IDENTITY_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
```

## 2. Gemini model compatibility note

Use the supported Vertex AI model ID `gemini-2.5-flash`.

This is the model name configured in the GKE Deployment manifest. Set the same value in local development when testing against Vertex AI.

## 3. Artifact Registry commands

These commands prepare container image storage in Google Artifact Registry.

```bash
gcloud auth application-default login
gcloud config set project "$PROJECT_ID"
gcloud services enable artifactregistry.googleapis.com container.googleapis.com
gcloud artifacts repositories create "$REPOSITORY_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="AI DevOps Agent container images"
gcloud auth configure-docker "$REGION-docker.pkg.dev"
```

Build and push the image only after explicit approval:

```bash
docker build -t "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/ai-devops-agent:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/ai-devops-agent:latest"
```

## 4. Workload Identity Federation for GKE

Do not store a Google Cloud service-account JSON key in the repository or container image.

Use GKE Workload Identity instead. The Kubernetes service account in the manifest should be mapped to a GCP service account with the minimum required IAM permissions.

```bash
gcloud iam service-accounts create "$WORKLOAD_IDENTITY_SA" \
  --project "$PROJECT_ID"

gcloud iam service-accounts add-iam-policy-binding \
  "$WORKLOAD_IDENTITY_EMAIL" \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:${PROJECT_ID}.svc.id.goog[ai-devops-agent/${WORKLOAD_IDENTITY_SA}]"

kubectl annotate serviceaccount \
  ai-devops-agent-sa \
  -n ai-devops-agent \
  iam.gke.io/gcp-service-account="$WORKLOAD_IDENTITY_EMAIL"
```

The GCP service account should be granted only the least-privilege roles required for Vertex AI access, for example the model access needed by the app, and the Kubernetes read-only cluster access handled by the RBAC manifest.

## 5. GKE Autopilot cluster creation

This command creates a billable GKE Autopilot cluster and must not be executed unless approved.

```bash
gcloud container clusters create-auto "$CLUSTER_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --network default \
  --subnetwork default
```

## 6. Kubernetes configuration

After the cluster exists, configure kubectl and deploy the resources in this repository:

```bash
gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$REGION" --project "$PROJECT_ID"
kubectl create namespace ai-devops-agent
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/serviceaccount.yaml
kubectl apply -f kubernetes/rbac.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
```

## 7. Application verification

```bash
kubectl get pods -n ai-devops-agent
kubectl get services -n ai-devops-agent
kubectl get deployment -n ai-devops-agent
kubectl port-forward -n ai-devops-agent svc/ai-devops-agent 8000:80
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/kubernetes/status
```

## 8. IAM and least-privilege notes

The application should use the Kubernetes service account identity and Google Cloud Application Default Credentials for local development.

Required read-only Kubernetes permissions are defined in the RBAC manifest and include only:
- get
- list
- watch

For Gemini / Vertex AI access, grant the least-privilege role necessary for the workload identity or service account used by the GKE workload. Avoid broad Owner or Editor roles.

## 9. Deployment process summary

1. Run project tests locally.
2. Build the Docker image.
3. Create Artifact Registry repository.
4. Push the Docker image.
5. Create the Autopilot GKE cluster.
6. Configure kubectl.
7. Apply namespace, service account, RBAC, deployment, and service manifests.
8. Verify pod health and readiness.
9. Verify the /health endpoint.
10. Verify the read-only Kubernetes inspection endpoints.

## 10. Cost awareness

The following commands may create billable resources:
- Artifact Registry repository creation
- GKE Autopilot cluster creation
- Cloud storage and networking resources created implicitly by GCP services

These commands must be executed only after explicit user approval.
