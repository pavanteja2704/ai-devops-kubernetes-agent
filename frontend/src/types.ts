export type JsonRecord = Record<string, unknown>;

export interface ClusterStatus {
  available: boolean;
  message: string;
  context: string;
}

export interface Pod {
  namespace?: string;
  name?: string;
  phase?: string;
  container_states?: Array<{ name?: string; state?: string }>;
  restart_counts?: Record<string, number>;
  node?: string;
  creation_timestamp?: string;
}

export interface Deployment {
  namespace?: string;
  name?: string;
  desired_replicas?: number;
  available_replicas?: number;
  ready_replicas?: number;
}

export interface Service {
  namespace?: string;
  name?: string;
  type?: string;
  cluster_ip?: string;
  ports?: Array<{ name?: string; port?: number; target_port?: string | number; protocol?: string }>;
}

export interface Node {
  name?: string;
  status?: string;
  kubernetes_version?: string;
  cpu_capacity?: string;
  memory_capacity?: string;
}

export interface Event {
  namespace?: string;
  name?: string;
  type?: string;
  reason?: string;
  message?: string;
  count?: number;
  first_timestamp?: string;
  last_timestamp?: string;
}

export interface AnalysisResult {
  status?: "critical" | "warning" | "healthy" | "unknown";
  problem?: {
    title?: string;
    resource_type?: string;
    resource_name?: string;
    namespace?: string;
    current_state?: string;
    impact?: string;
  };
  root_cause?: {
    summary?: string;
    confidence?: "high" | "medium" | "low";
    evidence?: string[];
  };
  recommended_actions?: Array<{
    priority?: number;
    title?: string;
    description?: string;
    command?: string;
    risk?: "low" | "medium" | "high";
  }>;
  what_not_to_do?: string[];
  verification?: Array<{ description?: string; command?: string }>;
  limitations?: string[];
}

export interface ClusterData {
  status: ClusterStatus;
  pods: Pod[];
  deployments: Deployment[];
  services: Service[];
  nodes: Node[];
  events: Event[];
}
