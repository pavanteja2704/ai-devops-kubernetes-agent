# Prompt 02 — Local Development Setup

You are continuing the AI DevOps Kubernetes Agent project.

Read the existing project structure before making changes.

## Objective

Prepare the application for local development and testing on Windows.

IMPORTANT:

- Do NOT create a GKE cluster.
- Do NOT create or modify any Google Cloud resources.
- Do NOT create Firebase resources.
- Do NOT deploy anything.
- Do NOT require a live Kubernetes cluster yet.
- Do NOT add write/modify/delete Kubernetes operations.
- Keep all Kubernetes functionality READ-ONLY.

## Python Environment

Use Python 3.12+.

Prepare the project for a Python virtual environment.

The application must support:

Windows development
+
Linux/Docker deployment later
+
GKE deployment later

Do not hard-code machine-specific paths.

## Dependencies

Review the existing requirements.txt.

Add only the dependencies actually required for the current application structure.

The project will eventually use:

- Kubernetes Python client
- Google Gen AI / Vertex AI SDK
- FastAPI
- Uvicorn
- Pydantic / configuration management
- python-dotenv if required

Do not add unnecessary packages.

Use currently supported stable package versions.

## Configuration

Review:

app/config/settings.py

and:

.env.example

Create a clean configuration system using environment variables.

Expected configuration categories:

GOOGLE_CLOUD_PROJECT
GOOGLE_CLOUD_LOCATION
GEMINI_MODEL
LOG_LEVEL

Do NOT put real credentials, API keys, passwords, tokens,
or project-specific secrets into source code.

Do NOT create a real .env file containing credentials.

Update .env.example with safe placeholder values only.

## Kubernetes Client

Review:

app/kubernetes/client.py

Prepare a Kubernetes client abstraction that can eventually support:

1. Local Kubernetes configuration
2. GKE authentication
3. Multiple Kubernetes clusters

For now, implement only the local development abstraction.

The code must fail gracefully if no Kubernetes cluster is available.

Do not attempt to create a cluster.

Do not modify Kubernetes resources.

## Application

Review:

app/main.py

and:

app/agent/agent.py

Create a minimal application that can start successfully
even when Kubernetes and Gemini are not configured.

The application should expose a simple health endpoint if FastAPI
is already part of the architecture.

Example:

GET /health

Expected response:

{
  "status": "healthy"
}

Do not implement AI troubleshooting yet.

Do not implement automatic remediation yet.

## Logging

Implement structured, useful application logging.

Avoid logging:

- credentials
- access tokens
- API keys
- sensitive environment variables

## Testing

Create basic unit tests for:

- configuration loading
- health endpoint
- Kubernetes client initialization/failure handling

Tests must NOT require a live GKE cluster.

Tests must NOT require real Gemini credentials.

## Code Quality

Use:

- Python type hints
- clear function names
- modular design
- useful docstrings where appropriate
- proper exception handling

Avoid unnecessary complexity.

## Validation

After implementing the changes:

1. Verify the Python files have valid syntax.
2. Verify imports.
3. Run the unit tests.
4. Start the application locally if possible.
5. Verify the health endpoint.

Do not deploy anything.

Do not create any cloud resources.

## Final Response

After completing the work, report:

1. Files created or modified.
2. Dependencies added.
3. Commands used for local setup.
4. Test results.
5. Whether the application starts successfully.
6. Any remaining issues.

STOP after completing this stage.
Do not proceed to Kubernetes deployment.