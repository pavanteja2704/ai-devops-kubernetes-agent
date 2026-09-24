# AI DevOps Kubernetes Agent

This is the final Step 16 application: a read-only FastAPI backend, React/Vite
Control Room, Kubernetes evidence collection, and structured Gemini incident
analysis. This guide is a completely manual deployment procedure for an
existing GKE cluster. It does not create clusters, discover clusters, deploy
automatically, use Fleet or Config Sync, or add remediation capabilities.

## Architecture

```text
Linux VM -- gcloud/kubectl/Docker --> existing GKE cluster
                                     +-- backend Deployment + ClusterIP Service
                                     |   read-only Kubernetes API + Vertex AI
                                     +-- frontend Deployment + LoadBalancer
                                         Nginx React SPA; /api/ proxies backend
```

The backend uses Workload Identity to call Vertex AI. Kubernetes RBAC allows
only `get`, `list`, and `watch`. Commands shown by the UI are recommendations
only and are never executed by the application.

## 1. Prerequisites

Use an Ubuntu/Debian Linux VM, adapting package commands for RHEL/Rocky/AlmaLinux
where necessary. Verify each tool:

```bash
sudo apt-get update
sudo apt-get install -y git docker.io
sudo systemctl enable --now docker
git --version
docker --version
docker run --rm hello-world
gcloud --version
gcloud components install kubectl gke-gcloud-auth-plugin
kubectl version --client
gke-gcloud-auth-plugin --version
```

Git clones the repository, Docker builds its two images, Google Cloud CLI
authenticates and manages GKE/IAM, `kubectl` applies and verifies manifests,
and the GKE plugin authenticates kubectl to GKE. Install Google Cloud CLI using
the official Linux instructions if it is not already installed.

## 2. Clone and configure inputs

```bash
git clone <repository-url>
cd <repository-directory>
```

Edit only [`deploy/inputs.yaml`](deploy/inputs.yaml). It contains placeholders
for the target GCP project, existing GKE cluster and zone/region, namespace,
runtime Google service account, Artifact Registry project/location/repository,
and backend/frontend image tags. It contains no credentials or secrets.

`project_id` is the GKE project. `artifact_registry.project_id` may be the same
or different. The GKE project owns the cluster; the Artifact Registry project
owns images. `google_service_account` is the runtime identity for Vertex AI,
not the GKE node image-pull identity.

The checked-in manifests contain the Step 16 example image/project values. For
a different environment, make temporary copies and substitute the values from
`inputs.yaml`; do not edit application source, frontend source, Dockerfiles, or
the checked-in Step 16 manifests.

## 3. Authenticate and verify the project

```bash
gcloud auth login
gcloud auth list
gcloud auth application-default login
gcloud config set project TARGET_GCP_PROJECT_ID
gcloud config get-value project
gcloud projects describe TARGET_GCP_PROJECT_ID
gcloud billing projects describe TARGET_GCP_PROJECT_ID
```

`gcloud auth login` authenticates the operator. Application Default Credentials
are for local Google client-library checks; they are not copied into Pods.
Project/billing and IAM commands may require administrator permissions.

## 4. Verify GKE and obtain credentials

```bash
gcloud container clusters list --project TARGET_GCP_PROJECT_ID
gcloud container clusters describe TARGET_GKE_CLUSTER_NAME \
  --location TARGET_GKE_LOCATION --project TARGET_GCP_PROJECT_ID
```

Use `--zone` for a zonal cluster or `--region` for a regional cluster:

```bash
gcloud container clusters get-credentials TARGET_GKE_CLUSTER_NAME \
  --zone TARGET_GKE_LOCATION --project TARGET_GCP_PROJECT_ID
# or:
gcloud container clusters get-credentials TARGET_GKE_CLUSTER_NAME \
  --region TARGET_GKE_LOCATION --project TARGET_GCP_PROJECT_ID
kubectl cluster-info
kubectl get nodes
```

## 5. Enable required APIs

Only these APIs are required by this repository:

```bash
gcloud services enable container.googleapis.com artifactregistry.googleapis.com \
  aiplatform.googleapis.com --project TARGET_GCP_PROJECT_ID
```

They provide GKE, Artifact Registry, and Vertex AI respectively. If Artifact
Registry is in another project, enable its API there too.

## 6. Vertex AI service account and Workload Identity

Create the runtime Google service account if needed:

```bash
gcloud iam service-accounts create ai-devops-agent-sa \
  --display-name="AI DevOps Kubernetes Agent runtime" \
  --project TARGET_GCP_PROJECT_ID
gcloud projects add-iam-policy-binding TARGET_GCP_PROJECT_ID \
  --member="serviceAccount:ai-devops-agent-sa@TARGET_GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/aiplatform.user
```

The only application role is `roles/aiplatform.user`; do not grant Owner,
Editor, `roles/container.admin`, or other broad roles.

For Autopilot, use the managed Workload Identity model and still configure the
service-account annotation and IAM binding below. For Standard GKE, verify the
cluster has a workload identity pool:

```bash
gcloud container clusters describe TARGET_GKE_CLUSTER_NAME \
  --location TARGET_GKE_LOCATION --project TARGET_GCP_PROJECT_ID \
  --format='yaml(workloadIdentityConfig)'
```

The existing [`kubernetes/serviceaccount.yaml`](kubernetes/serviceaccount.yaml)
contains the `iam.gke.io/gcp-service-account` annotation. If the target project
differs, create a temporary copy with the target service-account email.

```bash
gcloud iam service-accounts add-iam-policy-binding \
  ai-devops-agent-sa@TARGET_GCP_PROJECT_ID.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:TARGET_GCP_PROJECT_ID.svc.id.goog[ai-devops-agent/ai-devops-agent-sa]"
gcloud iam service-accounts get-iam-policy \
  ai-devops-agent-sa@TARGET_GCP_PROJECT_ID.iam.gserviceaccount.com
```

## 7. Namespace, ServiceAccount, and read-only RBAC

The actual Step 16 files are `kubernetes/namespace.yaml`,
`kubernetes/serviceaccount.yaml`, and `kubernetes/rbac.yaml`:

```bash
kubectl apply -f kubernetes/namespace.yaml
kubectl get namespace ai-devops-agent
kubectl apply -f kubernetes/serviceaccount.yaml
kubectl apply -f kubernetes/rbac.yaml
kubectl auth can-i get pods --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
kubectl auth can-i list pods --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
kubectl auth can-i get pods/log --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
kubectl auth can-i delete pods --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
kubectl auth can-i patch deployments --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
```

The first three checks should be `yes`; delete and patch must be `no`. The
agent has no delete, patch, exec, restart, scale, or apply permissions.

## 8. Artifact Registry and images

Create the Docker repository if it does not exist:

```bash
gcloud artifacts repositories create TARGET_ARTIFACT_REGISTRY_REPOSITORY \
  --repository-format=docker --location=TARGET_ARTIFACT_REGISTRY_LOCATION \
  --project=TARGET_ARTIFACT_REGISTRY_PROJECT_ID
gcloud auth configure-docker TARGET_ARTIFACT_REGISTRY_LOCATION-docker.pkg.dev
```

Build and push manually:

```bash
docker build -t TARGET_ARTIFACT_REGISTRY_LOCATION-docker.pkg.dev/TARGET_ARTIFACT_REGISTRY_PROJECT_ID/TARGET_ARTIFACT_REGISTRY_REPOSITORY/ai-devops-agent:latest .
docker push TARGET_ARTIFACT_REGISTRY_LOCATION-docker.pkg.dev/TARGET_ARTIFACT_REGISTRY_PROJECT_ID/TARGET_ARTIFACT_REGISTRY_REPOSITORY/ai-devops-agent:latest
docker build -t TARGET_ARTIFACT_REGISTRY_LOCATION-docker.pkg.dev/TARGET_ARTIFACT_REGISTRY_PROJECT_ID/TARGET_ARTIFACT_REGISTRY_REPOSITORY/ai-devops-frontend:latest frontend
docker push TARGET_ARTIFACT_REGISTRY_LOCATION-docker.pkg.dev/TARGET_ARTIFACT_REGISTRY_PROJECT_ID/TARGET_ARTIFACT_REGISTRY_REPOSITORY/ai-devops-frontend:latest
```

When GKE and Artifact Registry projects are the same, use the normal project
policy. When they differ, grant only `roles/artifactregistry.reader` to the
GKE node service account in the Artifact Registry project. This is distinct
from the runtime Google service account, which needs Vertex AI access. Do not
grant Artifact Registry Admin, Owner, or Editor.

## 9. Deploy the backend

The existing backend files are:

- [`kubernetes/deployment.yaml`](kubernetes/deployment.yaml)
- [`kubernetes/service.yaml`](kubernetes/service.yaml)
- [`kubernetes/namespace.yaml`](kubernetes/namespace.yaml)
- [`kubernetes/serviceaccount.yaml`](kubernetes/serviceaccount.yaml)
- [`kubernetes/rbac.yaml`](kubernetes/rbac.yaml)

After creating a temporary deployment copy with the target backend image and
project values, apply manually:

```bash
kubectl apply -f /tmp/ai-devops-deployment.yaml
kubectl apply -f kubernetes/service.yaml
```

The backend Service remains `ClusterIP`; it is not public.

## 10. Deploy the frontend

The existing files are [`kubernetes/frontend-deployment.yaml`](kubernetes/frontend-deployment.yaml)
and [`kubernetes/frontend-service.yaml`](kubernetes/frontend-service.yaml).
After creating a temporary deployment copy with the target frontend image:

```bash
kubectl apply -f /tmp/ai-devops-frontend-deployment.yaml
kubectl apply -f kubernetes/frontend-service.yaml
```

Nginx listens on 8080 and the LoadBalancer exposes port 80.

## 11. Verify the deployment

```bash
kubectl get pods -n ai-devops-agent
kubectl get deployments -n ai-devops-agent
kubectl get services -n ai-devops-agent
kubectl describe pod -n ai-devops-agent POD_NAME
kubectl get service ai-devops-frontend -n ai-devops-agent
kubectl get service ai-devops-frontend -n ai-devops-agent \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}{"\n"}'
```

For private backend verification:

```bash
kubectl port-forward service/ai-devops-agent 8000:80 -n ai-devops-agent
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/kubernetes/status
```

Open the frontend LoadBalancer address in a browser. In the Control Room, run
the health test and ask the existing troubleshooting questions. Verify that
structured status, problem, root cause, evidence, actions, verification,
warnings, and limitations appear. Copy buttons never execute commands.

## 12. Controlled failure test

Use only an approved test namespace or test Pod:

```bash
kubectl run ai-test-broken-image --image=nginx:this-image-does-not-exist \
  --restart=Never -n ai-devops-agent
kubectl get pod ai-test-broken-image -n ai-devops-agent -w
kubectl get events -n ai-devops-agent --sort-by=.lastTimestamp
```

Run the Control Room health test and confirm ImagePullBackOff/ErrImagePull,
unavailable logs, and read-only recommendations are visible. Clean up:

```bash
kubectl delete pod ai-test-broken-image -n ai-devops-agent
```

## 13. Troubleshooting

- **Missing auth plugin:** verify `gke-gcloud-auth-plugin --version`; install
  it with `gcloud components install gke-gcloud-auth-plugin`.
- **kubectl cannot connect:** verify `kubectl cluster-info`, current context,
  and rerun `get-credentials` with the correct zone/region.
- **Permission denied:** inspect the relevant project IAM policy and request
  the specific least-privilege role; never use Owner/Editor as a shortcut.
- **Workload Identity failure:** inspect the ServiceAccount annotation and
  `get-iam-policy`; correct the `roles/iam.workloadIdentityUser` binding.
- **Vertex AI denied:** verify `aiplatform.googleapis.com` and
  `roles/aiplatform.user` on the runtime identity.
- **ImagePullBackOff:** run `kubectl describe pod`; verify image path/tag and,
  for cross-project images, node identity `roles/artifactregistry.reader`.
- **Frontend LoadBalancer pending:** run `kubectl describe service`; inspect
  service events, quota, and cloud networking.
- **Backend unavailable:** inspect backend Pods, Service, readiness probes, and
  the private health checks above.
- **RBAC denied:** run the `kubectl auth can-i` checks; reapply the existing
  `kubernetes/rbac.yaml` without adding write verbs.
- **Pending/CrashLoopBackOff:** inspect `kubectl describe pod` and read-only
  logs; use the AI assessment for investigation, not automatic remediation.

## 14. Security and final checklist

Never commit service-account keys, passwords, API keys, or access tokens.
Prefer Workload Identity, least privilege, and read-only Kubernetes access.

- [ ] Prerequisites installed and verified
- [ ] Repository cloned and `deploy/inputs.yaml` configured
- [ ] Correct project and cluster verified
- [ ] Required APIs enabled
- [ ] Vertex AI and Workload Identity configured
- [ ] Namespace, ServiceAccount, and RBAC applied
- [ ] Artifact Registry access configured
- [ ] Backend and frontend deployed
- [ ] Health and Kubernetes status verified
- [ ] Frontend accessible
- [ ] AI troubleshooting tested
- [ ] Controlled failure tested and test resource removed

## Local validation

```bash
python -m pytest -q
cd frontend
npm test
npm run build
```
