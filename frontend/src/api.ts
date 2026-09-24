import type {
  AnalysisResult,
  ClusterData,
  ClusterStatus,
  Deployment,
  Event,
  Node,
  Pod,
  Service,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  status: () => request<ClusterStatus>("/kubernetes/status"),
  pods: () => request<Pod[]>("/kubernetes/pods"),
  deployments: () => request<Deployment[]>("/kubernetes/deployments"),
  services: () => request<Service[]>("/kubernetes/services"),
  nodes: () => request<Node[]>("/kubernetes/nodes"),
  events: () => request<Event[]>("/kubernetes/events"),
  logs: (namespace: string, podName: string, containerName?: string) =>
    request<{ logs: string }>(`/kubernetes/logs?namespace=${encodeURIComponent(namespace)}&pod_name=${encodeURIComponent(podName)}${
      containerName ? `&container_name=${encodeURIComponent(containerName)}` : ""
    }`),
  analyze: (question: string) =>
    request<AnalysisResult>("/analyze", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
};

export async function loadClusterData(): Promise<ClusterData> {
  const [, status, pods, deployments, services, nodes, events] = await Promise.all([
    api.health(),
    api.status(),
    api.pods(),
    api.deployments(),
    api.services(),
    api.nodes(),
    api.events(),
  ]);
  return { status, pods, deployments, services, nodes, events };
}

export { API_BASE_URL };
