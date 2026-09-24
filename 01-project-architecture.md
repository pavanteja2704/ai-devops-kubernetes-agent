# Prompt 01 — AI DevOps Kubernetes Agent Architecture

You are an expert Google Cloud, GKE, Kubernetes, Python,
DevOps, and AI agent engineer.

We are building an AI-powered DevOps Kubernetes troubleshooting
agent from scratch.

IMPORTANT:
Do not copy the architecture from an existing repository.
Use the requirements below and create a clean, modular architecture.

## Development Environment

Operating system:
Windows

IDE:
Visual Studio Code

AI coding assistant:
Gemini Code Assist

Programming language:
Python 3.12+

Cloud platform:
Google Cloud Platform

Future Kubernetes platform:
Google Kubernetes Engine (GKE)

AI model:
Google Gemini through the official Google Gen AI SDK / Vertex AI

Containerization:
Docker

Container registry:
Google Artifact Registry

## Important Architecture Requirement

The application must initially run locally for development and testing.

DO NOT create a GKE cluster.

DO NOT deploy anything to GKE.

DO NOT create Firebase resources.

DO NOT create Compute Engine resources.

DO NOT create cloud resources.

For this step, only create the application architecture,
source code structure, configuration files, and documentation.

## Future Architecture

The final application will eventually run as a Kubernetes Pod
inside GKE.

The agent will:

1. Connect to Kubernetes clusters.
2. Collect Kubernetes information.
3. Analyze cluster problems using Gemini.
4. Explain the probable root cause.
5. Recommend remediation steps.
6. Eventually support multiple GKE clusters.
7. Initially operate in READ-ONLY mode.

The agent must NOT automatically modify or delete
Kubernetes resources.

## Kubernetes Information

The agent should eventually be capable of collecting:

- Cluster information
- Nodes
- Namespaces
- Pods
- Deployments
- ReplicaSets
- Services
- ConfigMaps
- Events
- Pod logs
- Pod status
- Container restart counts
- Container states
- Resource requests and limits

## AI Agent Flow

The intended flow is:

User
  ↓
Agent API
  ↓
Kubernetes Information Collector
  ↓
Kubernetes API
  ↓
Collected cluster information
  ↓
Gemini
  ↓
Root Cause Analysis
  ↓
Recommended Remediation
  ↓
Response to User

## Project Structure

Create a clean structure similar to:

ai-devops-kubernetes-agent/

├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   └── agent.py
│   │
│   ├── kubernetes/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── pods.py
│   │   ├── nodes.py
│   │   ├── deployments.py
│   │   ├── events.py
│   │   └── logs.py
│   │
│   ├── gemini/
│   │   ├── __init__.py
│   │   └── client.py
│   │
│   └── config/
│       ├── __init__.py
│       └── settings.py
│
├── prompts/
│   └── system_prompt.txt
│
├── tests/
│
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md

## Coding Requirements

Use clean Python code.

Use type hints.

Use environment variables for configuration.

Never hard-code:

- Google Cloud project IDs
- Cluster names
- API keys
- Credentials
- Passwords
- Tokens

Create `.env.example` containing placeholders only.

Create useful error handling.

Create logging.

Keep Kubernetes functionality separate from Gemini functionality.

Keep the AI agent logic separate from the API layer.

Keep the code modular so that we can later add
multi-cluster support.

## Multi-Cluster Requirement

The final architecture should support:

GKE Cluster A
       ↑
       │
AI Agent
       │
       ↓
GKE Cluster B

The agent should eventually be able to inspect multiple
Kubernetes clusters using controlled authentication and
Kubernetes RBAC.

However, DO NOT implement multi-cluster access yet.

## Security

The initial agent must be READ-ONLY.

Do not implement:

- delete
- restart
- scale
- patch
- exec into containers
- modify deployments

Those capabilities may be considered later.

## Deliverables

Create the complete project structure and the minimum
starter files required for the application.

Do not create unnecessary code.

Do not deploy anything.

Do not create GCP resources.

After creating the files, explain:

1. What each folder does.
2. What each file does.
3. How the components will communicate.
4. What we will implement in the next step.

Wait for further instructions before implementing
the next major feature.