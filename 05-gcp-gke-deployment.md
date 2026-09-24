# Prompt 05 — GCP, Containerization and GKE Deployment

Continue the existing AI DevOps Kubernetes Agent project.

Read all existing source code before making changes.

## Objective

Prepare the AI DevOps Kubernetes Agent to run as a containerized
application inside Google Kubernetes Engine (GKE).

The final architecture is:

Developer Laptop
       |
       | VS Code / Git
       |
       v
Docker Image
       |
       v
Artifact Registry
       |
       v
GKE Autopilot
       |
       v
AI DevOps Agent Pod
       |
       +---- Kubernetes API
       |
       +---- Gemini / Vertex AI

## IMPORTANT SAFETY REQUIREMENTS

The agent must remain READ-ONLY regarding Kubernetes resources.

The agent must NOT:

- delete resources
- restart pods
- scale deployments
- patch resources
- modify deployments
- execute commands inside containers

The AI model must only analyze Kubernetes information.

It must provide recommendations rather than execute remediation.

## GCP Project

Use the existing Google Cloud project through configuration.

Do NOT hard-code the project ID into Python source code.

Use:

GOOGLE_CLOUD_PROJECT

The current development project is:

ai-agent-509509

Treat this as configuration only.

## Google Cloud Authentication

Use Google Cloud Application Default Credentials for local development.

Do not create API keys.

Do not put credentials into source code.

Do not commit credentials.

For GKE, design the application to use the Pod's Google
Cloud identity rather than storing a service account key.

## Docker

Review the existing Dockerfile.

Create a production-ready Python container.

Requirements:

- Python 3.12+
- non-root container user
- minimal image
- no credentials inside image
- environment-based configuration
- application starts with the correct command
- health endpoint available

## Artifact Registry

Prepare the commands/documentation required to:

1. Create an Artifact Registry Docker repository.
2. Authenticate Docker.
3. Build the Docker image.
4. Tag the image.
5. Push the image to Artifact Registry.

DO NOT execute resource-creation commands automatically.

Show the commands first.

Use placeholders where appropriate.

## GKE

The target platform is:

Google Kubernetes Engine Autopilot.

Target region:

us-central1

Cluster name:

ai-devops-agent

IMPORTANT:

Do NOT automatically create the GKE cluster.

First provide the exact command that would create it.

The user will manually approve the command before execution.

## Kubernetes Deployment

Create Kubernetes manifests for:

- Namespace
- ServiceAccount
- Deployment
- Service

The Deployment must run the AI DevOps Agent.

Use:

- resource requests
- resource limits
- readiness probe
- liveness probe
- security context
- non-root execution where supported

Do not use privileged containers.

## Kubernetes RBAC

The agent must have READ-ONLY Kubernetes permissions.

Create a Role/ClusterRole that permits only read operations such as:

get
list
watch

on appropriate resources.

Required resource categories may include:

- pods
- pods/log
- nodes
- namespaces
- deployments
- replicasets
- services
- events
- configmaps

Do NOT grant:

create
update
patch
delete
deletecollection

Do NOT grant wildcard write permissions.

## Gemini / Vertex AI

Configure the deployed agent to use Google's Gemini capability
through the application's existing Gemini abstraction.

Do not expose credentials to the container.

Prepare the required Google Cloud identity configuration.

If additional IAM permissions are required, document them.

Do NOT automatically grant broad Owner or Editor roles.

Use least privilege.

## Application Configuration

Use environment variables or Kubernetes configuration.

Do not put secrets in:

- Python source
- Dockerfile
- Git
- Kubernetes manifests

## Multi-Cluster Architecture

The first deployment should inspect only the GKE cluster
where the agent is running.

Do NOT implement multi-cluster access yet.

However, keep the architecture extensible so that later we
can support:

Agent Cluster
      |
      +---- GKE Cluster A
      |
      +---- GKE Cluster B
      |
      +---- GKE Cluster C

## Deployment Process

Prepare a clear deployment procedure:

1. Build application
2. Run tests
3. Build Docker image
4. Create Artifact Registry repository
5. Push image
6. Create GKE Autopilot cluster
7. Configure kubectl
8. Create Kubernetes namespace
9. Configure ServiceAccount/RBAC
10. Deploy application
11. Verify Pod
12. Verify Service
13. Test /health
14. Test Kubernetes read-only inspection
15. Test Gemini analysis

## Cost Awareness

Before any GCP resource creation:

Clearly display the commands that create billable resources.

Do not execute them automatically.

The user must explicitly approve resource creation.

## Validation

Before deployment:

Run:

- Python syntax validation
- all unit tests
- Docker build validation if Docker is available

After deployment:

Verify:

kubectl get pods
kubectl get services
kubectl get deployment

Then verify the application health endpoint.

## Final Response

Report:

1. Files created/modified.
2. Docker configuration.
3. Artifact Registry commands.
4. GKE commands.
5. Kubernetes manifests.
6. RBAC permissions.
7. Required IAM permissions.
8. Deployment steps.
9. Cost-related resources.
10. Tests performed.

IMPORTANT:

STOP BEFORE CREATING ANY GCP RESOURCE.

Show the resource-creation commands to the user first
and wait for explicit approval.