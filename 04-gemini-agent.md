# Prompt 04 — Gemini AI Analysis Engine

Continue the existing AI DevOps Kubernetes Agent project.

Read the complete existing project structure before making changes.

## Objective

Implement the AI reasoning layer using Google's Gemini model.

The agent must analyze Kubernetes information and provide:

1. Problem summary
2. Observed evidence
3. Probable root cause
4. Recommended remediation steps
5. Confidence/limitations

IMPORTANT:

- Do NOT create a GKE cluster.
- Do NOT create any Google Cloud resources.
- Do NOT create Firebase resources.
- Do NOT deploy anything.
- Do NOT modify Kubernetes resources.
- Do NOT delete Kubernetes resources.
- Do NOT restart pods.
- Do NOT scale deployments.
- Keep Kubernetes operations READ-ONLY.

## Gemini Integration

Review:

app/gemini/client.py

Implement a clean Gemini client abstraction using Google's
supported Gen AI / Vertex AI SDK.

Do not hard-code:

- Project ID
- Credentials
- API keys
- Tokens
- Secrets

Configuration must come from environment variables.

Use the existing configuration system.

Expected configuration:

GOOGLE_CLOUD_PROJECT
GOOGLE_CLOUD_LOCATION
GEMINI_MODEL

Do not require a real Gemini credential for unit tests.

## AI Agent

Review:

app/agent/agent.py

Implement the agent reasoning workflow.

The agent should accept structured Kubernetes information such as:

- cluster information
- nodes
- pods
- deployments
- services
- events
- logs

It should construct a clear analysis request for Gemini.

The prompt must instruct Gemini to:

- analyze only the supplied evidence
- distinguish observed facts from assumptions
- identify probable root causes
- avoid inventing Kubernetes information
- provide practical remediation guidance
- clearly state when evidence is insufficient
- NEVER execute remediation actions

## System Prompt

Review:

prompts/system_prompt.txt

Create a strong system prompt defining the agent as:

"An AI-powered Kubernetes DevOps troubleshooting assistant."

The assistant is:

- read-only
- evidence-driven
- security-conscious
- conservative when evidence is insufficient

It must never claim that an action was performed.

It should say:

"Recommended action: ..."

instead of:

"I restarted the pod."

## Analysis API

Add an endpoint such as:

POST /analyze

Input example:

{
  "question": "Why is my application pod restarting?",
  "context": {
    "pods": [],
    "events": [],
    "logs": []
  }
}

The API should pass the supplied evidence to the agent.

Return structured output similar to:

{
  "summary": "...",
  "evidence": [],
  "probable_root_cause": "...",
  "recommendations": [],
  "limitations": []
}

Do not expose credentials or internal secrets.

## No Live Gemini Requirement for Tests

Unit tests must work without a real Gemini API call.

Mock the Gemini client.

Create tests for:

- successful analysis
- Gemini unavailable
- malformed input
- insufficient evidence
- error handling

## Security

Never send:

- API keys
- credentials
- environment secrets

to the model.

Do not allow the model to directly execute:

- kubectl
- gcloud
- shell commands
- Python commands

The model only analyzes data supplied by the application.

## Local Development

The application must continue starting successfully even if:

- Gemini credentials are unavailable
- Kubernetes is unavailable

The health endpoint must continue working.

## Validation

Run:

1. Python syntax validation
2. Unit tests
3. Application startup test

If Gemini credentials are unavailable, use mocked tests.

Do NOT create cloud resources.

Do NOT deploy anything.

## Final Response

Report:

1. Files created/modified.
2. Gemini integration implemented.
3. Agent reasoning flow.
4. API endpoints added.
5. Tests executed.
6. Test results.
7. Any remaining limitations.

STOP after completing this stage.