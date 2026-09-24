# Prompt 03 — Kubernetes Connectivity and Read-Only Inspection

Continue the AI DevOps Kubernetes Agent project.

Read the existing project structure and code before making changes.

## Objective

Implement the Kubernetes connectivity and READ-ONLY inspection layer.

The application must be capable of connecting to a Kubernetes cluster
using the Kubernetes Python client.

IMPORTANT:

- Do NOT create a GKE cluster.
- Do NOT create any Google Cloud resources.
- Do NOT create Firebase resources.
- Do NOT deploy anything.
- Do NOT modify Kubernetes resources.
- Do NOT delete Kubernetes resources.
- Do NOT restart pods.
- Do NOT scale deployments.
- Do NOT patch resources.
- Do NOT execute commands inside containers.

All Kubernetes operations must remain READ-ONLY.

## Authentication

Design the Kubernetes client to support:

1. Local kubeconfig authentication during development.
2. In-cluster authentication when the application is eventually
   deployed as a Pod in GKE.

Use the Kubernetes Python client's standard authentication mechanisms.

Do not hard-code credentials.

Do not store kubeconfig files in the repository.

Do not commit credentials.

## Kubernetes Client

Review and improve:

app/kubernetes/client.py

Create a clean Kubernetes client abstraction.

It should:

- Detect whether a local kubeconfig is available.
- Load the local kubeconfig when available.
- Gracefully handle the absence of a Kubernetes cluster.
- Support in-cluster configuration for future GKE deployment.
- Provide useful logging.
- Never expose credentials in logs.

## Read-Only Collectors

Implement read-only collectors for:

### Cluster

Collect:

- Kubernetes version
- API server information where available

### Nodes

Collect:

- node name
- status
- Kubernetes version
- CPU capacity
- memory capacity

### Namespaces

Collect:

- namespace names

### Pods

Collect:

- namespace
- pod name
- phase
- container states
- restart counts
- node
- creation timestamp

### Deployments

Collect:

- namespace
- deployment name
- desired replicas
- available replicas
- ready replicas

### Services

Collect:

- namespace
- service name
- service type
- cluster IP
- ports

### Events

Collect recent Kubernetes events.

### Logs

Implement a safe method for reading logs from a specified pod
and container.

Do not execute commands inside containers.

## Error Handling

If Kubernetes is unavailable, the application must NOT crash.

Return a structured response such as:

{
    "available": false,
    "message": "Kubernetes cluster is not available"
}

When Kubernetes is available:

{
    "available": true
}

Use appropriate exception handling.

## API

Add read-only API endpoints where appropriate.

For example:

GET /health

GET /kubernetes/status

GET /kubernetes/nodes

GET /kubernetes/namespaces

GET /kubernetes/pods

GET /kubernetes/deployments

GET /kubernetes/services

GET /kubernetes/events

Do not expose write operations.

## Testing

Create unit tests using mocks.

Tests must NOT require a real Kubernetes cluster.

Test:

- Kubernetes client initialization
- unavailable cluster handling
- node collection
- pod collection
- deployment collection
- event collection
- error handling

Use mocked Kubernetes API responses.

## Local Testing

If a local Kubernetes cluster is available, you may test
read-only operations against it.

However, do NOT create a local cluster automatically.

Do not require Docker Desktop Kubernetes,
Minikube, Kind, or GKE for the tests.

## Security

The application must remain read-only.

Do not implement:

- create
- update
- patch
- delete
- scale
- restart
- exec

## Final Validation

Run:

- Python syntax validation
- Unit tests
- Application startup validation

If no Kubernetes cluster is available, that is acceptable.

The application should still start successfully.

Report:

1. Files created/modified.
2. Kubernetes functionality implemented.
3. Tests executed.
4. Test results.
5. Whether a Kubernetes cluster was available.
6. Any remaining issues.

STOP after completing this stage.

Do not create or deploy a GKE cluster.