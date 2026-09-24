# AI DevOps Kubernetes Agent

The final Step 16 application is a read-only FastAPI backend, React/Vite
Control Room, Kubernetes evidence collector, and structured Gemini incident
troubleshooter. This repository adds a portable deployment wrapper without
changing that application behavior.


## Deployment model

The operator supplies only a GCP project ID, existing GKE cluster name, and
explicit cluster location in
[`deploy/inputs.yaml`](deploy/inputs.yaml), then runs:

```powershell
.\deploy\deploy.ps1
```

The script determines whether the supplied location is zonal or regional,
derives the Artifact Registry location, image
URIs, Google service-account email, and Workload Identity member. It validates
capacity, enables only required APIs, builds and pushes the existing images,
renders temporary manifests, applies the existing Kubernetes resources, waits
for both rollouts, and prints the frontend URL.

There is no application-level cluster discovery, multi-cluster routing, Fleet,
Config Sync, cluster selector, `cluster_id`, or automatic remediation.

## Architecture and safety

```text
Operator VM -> gcloud / Docker / kubectl -> existing GKE cluster
                                      +-- FastAPI backend (ClusterIP)
                                      |   read-only Kubernetes API + Vertex AI
                                      +-- Nginx React frontend (LoadBalancer)
```

The backend uses Workload Identity to call Vertex AI Gemini. Kubernetes RBAC
allows only `get`, `list`, and `watch` for Pods, Pod logs, Nodes, Namespaces,
Services, Events, Deployments, and ReplicaSets. The agent cannot delete,
patch, apply, scale, restart, or exec. Commands displayed by the AI are
recommendations only.

## 1. Prerequisites

Run the deployment from a Windows PowerShell workstation with:

- Google Cloud CLI (`gcloud`)
- `kubectl`
- Docker Desktop with a running daemon
- GKE authentication plugin

Verify:

```powershell
gcloud --version
kubectl version --client
gke-gcloud-auth-plugin --version
docker --version
docker info
```

The script fails before deployment if any tool is missing or Docker is not
running. A Linux VM can run the same workflow with PowerShell 7 installed;
adapt package installation to the distribution.

## 2. Configure the only input file

Edit only [`deploy/inputs.yaml`](deploy/inputs.yaml):

```yaml
project_id: "my-project-id"
cluster:
  name: "my-existing-gke-cluster"
  location: "us-central1-a"
```

`cluster.location` must be the existing cluster's zone, such as
`us-central1-a`, or region, such as `us-central1`. The script validates the
cluster at that exact location before continuing.

Do not add credentials, API keys, JSON keys, repository names,
service-account emails, image URIs, or IAM member strings. The script derives
those values.

## 3. Authenticate

```powershell
gcloud auth login
gcloud auth list
gcloud auth application-default login
```

The operator needs permission to inspect and administer the target project,
GKE cluster, Artifact Registry, IAM service account, and Vertex AI API. Do not
grant Owner or Editor as a shortcut.

## 4. Cluster capacity prerequisite

The complete application requests 350m CPU and 384Mi memory across backend and
frontend. The recommended target is at least:

- 1 node
- 4 vCPU
- 8 GB RAM

`deploy.ps1` reads every node's allocatable CPU and memory before creating
images or applying resources. Because Kubernetes and GKE reserve some
resources for system components, the script requires at least 3,500m
allocatable CPU and 8,192Mi allocatable memory. This is a deployment minimum,
not a requirement that allocatable CPU equal the node's physical CPU size.
The recommended node size remains at least 4 vCPU / 8 GiB. The script stops
and prints the detected nodes when the deployment minimum is not met. It never
resizes or recreates a node pool automatically.

Inspect manually:

```powershell
gcloud container clusters list --project PROJECT_ID
kubectl get nodes
kubectl describe nodes
```

## 5. What `deploy.ps1` does

In deterministic order, the script:

1. Reads and validates `deploy/inputs.yaml`.
2. Checks `gcloud`, `kubectl`, Docker, Docker daemon, and active gcloud auth.
3. Sets the active gcloud project.
4. Validates the supplied cluster location, determines whether it is zonal or regional, and gets credentials.
5. Verifies kubectl connectivity.
6. Checks allocatable node capacity.
7. Enables `container.googleapis.com`, `artifactregistry.googleapis.com`, and
   `aiplatform.googleapis.com` in the target project only.
8. Creates `ai-devops-agent-repo` if absent.
9. Configures Docker authentication for the derived regional registry host.
10. Builds and pushes `ai-devops-agent` and `ai-devops-frontend`.
11. Creates `ai-devops-agent-sa` if absent and grants only `roles/aiplatform.user`.
12. Ensures the Workload Identity pool is configured; for Standard clusters
    it automatically enables GKE Workload Identity Federation on an existing
    Standard cluster when `workloadIdentityConfig.workloadPool` is missing,
    then verifies the pool is `<PROJECT_ID>.svc.id.goog`. For Standard
    clusters, it checks every existing node pool and enables the GKE metadata
    server with `GKE_METADATA` only where needed. Autopilot must already
    report the expected Workload Identity pool.
13. Creates the namespace and annotated Kubernetes ServiceAccount.
14. Applies the existing read-only RBAC.
15. Renders temporary backend/frontend manifests with derived values.
16. Applies the backend, waits for readiness, and applies the ClusterIP Service.
17. Applies the frontend, waits for readiness, and applies the LoadBalancer Service.
18. Waits for the external address and prints the dashboard URL.
19. Prints final nodes, Pods, and Services.

Temporary rendered files are removed when the script exits. No credentials are
written to disk.

## 6. Run deployment

From the repository root:

```powershell
.\deploy\deploy.ps1
```

Derived image format:

```text
REGION-docker.pkg.dev/PROJECT_ID/ai-devops-agent-repo/ai-devops-agent:latest
REGION-docker.pkg.dev/PROJECT_ID/ai-devops-agent-repo/ai-devops-frontend:latest
```

The Artifact Registry region is the GKE region; a supplied zonal location such as
`us-central1-a` becomes `us-central1`.

## 7. Workload Identity and least privilege

The Google service account is:

```text
ai-devops-agent-sa@PROJECT_ID.iam.gserviceaccount.com
```

The Kubernetes ServiceAccount is `ai-devops-agent-sa` in namespace
`ai-devops-agent`, annotated with that email. The script grants:

- `roles/aiplatform.user` to the Google runtime service account.
- `roles/iam.workloadIdentityUser` for
  `PROJECT_ID.svc.id.goog[ai-devops-agent/ai-devops-agent-sa]`.

It never creates service-account keys. For cross-project Artifact Registry,
the GKE node identity, not the runtime identity, needs the minimum
`roles/artifactregistry.reader` role in the registry project.

Verify the application RBAC:

```powershell
kubectl auth can-i get pods --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
kubectl auth can-i list pods --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
kubectl auth can-i get pods/log --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
kubectl auth can-i delete pods --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
kubectl auth can-i patch deployments --as=system:serviceaccount:ai-devops-agent:ai-devops-agent-sa
```

The first three must be `yes`; delete and patch must be `no`.

## 8. Verification

```powershell
kubectl get nodes
kubectl get pods -n ai-devops-agent
kubectl get deployments -n ai-devops-agent
kubectl get svc -n ai-devops-agent
kubectl rollout status deployment/ai-devops-agent -n ai-devops-agent
kubectl rollout status deployment/ai-devops-frontend -n ai-devops-agent
kubectl get svc ai-devops-frontend -n ai-devops-agent
```

For private backend checks:

```powershell
kubectl port-forward service/ai-devops-agent 8000:80 -n ai-devops-agent
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/kubernetes/status
```

Open the external LoadBalancer address printed by the script. Run the
Dashboard health test and ask the existing Troubleshooter questions. Confirm
the structured status, problem, root cause, evidence, recommendations,
verification, warnings, and limitations cards appear.

## 9. Intentional ImagePullBackOff test

This test creates a deliberately broken deployment. Run it only when approved:

```powershell
kubectl create deployment agent-test-broken `
  --image=nginx:this-image-does-not-exist `
  -n ai-devops-agent
kubectl get pod -n ai-devops-agent -l app=agent-test-broken -w
kubectl get events -n ai-devops-agent --sort-by=.lastTimestamp
```

Run the AI health test and confirm `ErrImagePull`/`ImagePullBackOff` remains
visible while unavailable logs are recorded as non-fatal evidence. The agent
does not fix the deployment automatically. A human may repair the test:

```powershell
kubectl set image deployment/agent-test-broken `
  agent-test-broken=nginx:latest `
  -n ai-devops-agent
kubectl delete deployment agent-test-broken -n ai-devops-agent
```

## 10. Troubleshooting

- **Missing plugin:** install the GKE authentication plugin and verify its version.
- **kubectl connection failure:** rerun credential retrieval and check the
  discovered zone/region.
- **Insufficient CPU:** inspect `kubectl get nodes`; add capacity manually.
  Do not lower application requests or resize automatically.
- **ImagePullBackOff:** inspect `kubectl describe pod`; verify the derived
  Artifact Registry path, tag, Docker authentication, and node reader access.
- **Workload Identity failure:** inspect the Kubernetes annotation, workload
  pool, IAM policy binding, and backend Pod events.
- **Vertex AI denied:** verify the API and `roles/aiplatform.user` on the
  runtime Google service account.
- **LoadBalancer pending:** inspect
  `kubectl describe service ai-devops-frontend -n ai-devops-agent` and service
  events; cloud provisioning or quota may be pending.
- **Backend unavailable:** inspect backend readiness, Service selectors, and
  `/health` through the private port-forward.
- **RBAC Forbidden:** reapply the existing `kubernetes/rbac.yaml`; never add
  write verbs.

## 11. Reproduce on another laptop/project/cluster

Clone the repository, install and authenticate the prerequisites, change only
`deploy/inputs.yaml`, then run `.\deploy\deploy.ps1`. The script derives all
project-specific image, identity, and manifest values from the supplied
project and cluster location. It does not
require source or manifest edits.

## Local validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run build
```
