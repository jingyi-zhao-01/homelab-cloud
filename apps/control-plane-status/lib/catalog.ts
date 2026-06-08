export type ServiceKind = "deployment" | "worker" | "cronjob";
export type ServiceStatus = "active" | "degraded" | "inactive" | "scheduled" | "unknown";

export type ServiceDefinition = {
  id: string;
  name: string;
  kind: ServiceKind;
  description: string;
  deploymentName?: string;
  cronJobName?: string;
  serviceName?: string;
  enabledByDefault: boolean;
};

export type WorkloadDefinition = {
  id: string;
  name: string;
  namespace: string;
  description: string;
  services: ServiceDefinition[];
};

export type ServiceSnapshot = ServiceDefinition & {
  status: ServiceStatus;
  source: "catalog" | "cluster";
  summary: string;
  desiredReplicas?: number;
  availableReplicas?: number;
  lastRun?: {
    status: "succeeded" | "failed" | "running" | "unknown";
    finishedAt?: string;
  };
};

export type WorkloadSnapshot = Omit<WorkloadDefinition, "services"> & {
  status: ServiceStatus;
  source: "catalog" | "cluster";
  activeServices: number;
  totalServices: number;
  services: ServiceSnapshot[];
};

export const workloadCatalog: WorkloadDefinition[] = [
  {
    id: "flashsales",
    name: "Flashsales",
    namespace: "flashsales",
    description:
      "FastAPI concurrency practice workload with three user-facing services and one background order worker.",
    services: [
      {
        id: "user-service",
        name: "User Service",
        kind: "deployment",
        deploymentName: "flashsales-user-service",
        serviceName: "flashsales-user-service",
        description: "User CRUD, validation, and health probes.",
        enabledByDefault: true,
      },
      {
        id: "product-service",
        name: "Product Service",
        kind: "deployment",
        deploymentName: "flashsales-product-service",
        serviceName: "flashsales-product-service",
        description: "Catalog inventory, reservation, and release flow.",
        enabledByDefault: true,
      },
      {
        id: "order-service",
        name: "Order Service",
        kind: "deployment",
        deploymentName: "flashsales-order-service",
        serviceName: "flashsales-order-service",
        description: "Cross-service order orchestration and public API surface.",
        enabledByDefault: true,
      },
      {
        id: "order-worker",
        name: "Order Worker",
        kind: "worker",
        deploymentName: "flashsales-order-worker",
        description: "Background terminalization and async recovery tasks.",
        enabledByDefault: true,
      },
    ],
  },
  {
    id: "leetcode-intelligence",
    name: "LeetCode Intelligence",
    namespace: "leetcode-intelligence",
    description:
      "Continuous intelligence workload for prompt dispatch, recommendation, and long-running listener processes.",
    services: [
      {
        id: "intelligence-server",
        name: "Intelligence Server",
        kind: "deployment",
        deploymentName: "leetcode-intelligence-server",
        serviceName: "leetcode-intelligence",
        description: "Primary HTTP API and orchestration surface.",
        enabledByDefault: true,
      },
      {
        id: "prompt-dispatch",
        name: "Prompt Dispatch",
        kind: "worker",
        deploymentName: "leetcode-intelligence-prompt-dispatch",
        description: "Schedules and emits prompt dispatch jobs.",
        enabledByDefault: true,
      },
      {
        id: "prompt-listener",
        name: "Prompt Listener",
        kind: "worker",
        deploymentName: "leetcode-intelligence-prompt-listener",
        description: "Long-lived listener process for inbound prompt events.",
        enabledByDefault: true,
      },
      {
        id: "recommender",
        name: "Recommender",
        kind: "worker",
        deploymentName: "leetcode-intelligence-recommender",
        description: "Recommendation generation and ranking workload.",
        enabledByDefault: true,
      },
      {
        id: "submission-service",
        name: "Submission Service",
        kind: "deployment",
        deploymentName: "leetcode-intelligence-submission",
        serviceName: "leetcode-intelligence-submission",
        description: "Optional submission tracking API; currently disabled by chart default.",
        enabledByDefault: false,
      },
    ],
  },
  {
    id: "strategy-tester",
    name: "Strategy Tester",
    namespace: "strategy-tester",
    description:
      "Scheduled ingestion workload where status is defined by CronJob readiness and the last observed execution result.",
    services: [
      {
        id: "option-ingestor",
        name: "Option Ingestor",
        kind: "cronjob",
        cronJobName: "strategy-tester-option-ingestor",
        description: "Option contract metadata ingestion from Polygon.",
        enabledByDefault: true,
      },
      {
        id: "snapshot-ingestor",
        name: "Snapshot Ingestor",
        kind: "cronjob",
        cronJobName: "strategy-tester-snapshot-ingestor",
        description: "Snapshot ingestion for option market data and portfolio state.",
        enabledByDefault: true,
      },
    ],
  },
];
