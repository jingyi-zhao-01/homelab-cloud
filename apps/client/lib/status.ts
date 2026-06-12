import {
  AppsV1Api,
  BatchV1Api,
  KubeConfig,
  type V1CronJob,
  type V1Deployment,
} from "@kubernetes/client-node";
import {
  type ServiceDefinition,
  type ServiceSnapshot,
  type ServiceStatus,
  type WorkloadSnapshot,
  workloadCatalog,
} from "@/lib/catalog";

type LastRunState = ServiceSnapshot["lastRun"];

export type DashboardSnapshot = {
  generatedAt: string;
  source: "catalog" | "cluster";
  workloads: WorkloadSnapshot[];
};

function getKubeConfigFromEnv(): KubeConfig | null {
  const inlineConfig = process.env.KUBECONFIG_YAML;
  const base64Config = process.env.KUBECONFIG_BASE64;

  if (!inlineConfig && !base64Config) {
    return null;
  }

  const kubeConfigText = inlineConfig ?? Buffer.from(base64Config!, "base64").toString("utf8");
  const kubeConfig = new KubeConfig();
  kubeConfig.loadFromString(kubeConfigText);
  return kubeConfig;
}

function summarizeCatalogService(service: ServiceDefinition): ServiceSnapshot {
  const baseMessage =
    service.kind === "cronjob"
      ? "Schedule defined in chart. Add kubeconfig env vars to show the last cluster run."
      : service.enabledByDefault
        ? "Declared in repo and expected to run when the namespace is deployed."
        : "Defined in repo but disabled by the chart default values.";

  return {
    ...service,
    status: service.kind === "cronjob" ? "scheduled" : service.enabledByDefault ? "unknown" : "inactive",
    source: "catalog",
    summary: baseMessage,
  };
}

function deriveDeploymentStatus(deployment: V1Deployment | undefined): Pick<ServiceSnapshot, "status" | "summary" | "desiredReplicas" | "availableReplicas"> {
  if (!deployment) {
    return {
      status: "inactive",
      summary: "Deployment was not found in the cluster namespace.",
      desiredReplicas: 0,
      availableReplicas: 0,
    };
  }

  const desiredReplicas = deployment.spec?.replicas ?? 0;
  const availableReplicas = deployment.status?.availableReplicas ?? 0;

  if (desiredReplicas === 0) {
    return {
      status: "inactive",
      summary: "Deployment exists but is scaled to zero replicas.",
      desiredReplicas,
      availableReplicas,
    };
  }

  if (availableReplicas >= desiredReplicas) {
    return {
      status: "active",
      summary: `Healthy deployment with ${availableReplicas}/${desiredReplicas} replicas available.`,
      desiredReplicas,
      availableReplicas,
    };
  }

  return {
    status: "degraded",
    summary: `Deployment is not fully ready yet: ${availableReplicas}/${desiredReplicas} replicas available.`,
    desiredReplicas,
    availableReplicas,
  };
}

function getLastRun(jobs: Array<{ name?: string; status?: LastRunState }>): LastRunState {
  if (jobs.length === 0) {
    return {
      status: "unknown",
    };
  }

  return jobs[0].status ?? { status: "unknown" };
}

function deriveCronJobStatus(cronJob: V1CronJob | undefined, lastRun: LastRunState): Pick<ServiceSnapshot, "status" | "summary" | "lastRun"> {
  if (!cronJob) {
    return {
      status: "inactive",
      summary: "CronJob was not found in the cluster namespace.",
      lastRun,
    };
  }

  if (cronJob.spec?.suspend) {
    return {
      status: "inactive",
      summary: "CronJob exists but is suspended.",
      lastRun,
    };
  }

  if (lastRun?.status === "failed") {
    return {
      status: "degraded",
      summary: "CronJob is scheduled, but the most recent observed run failed.",
      lastRun,
    };
  }

  if (lastRun?.status === "running") {
    return {
      status: "active",
      summary: "CronJob is scheduled and currently has an active run.",
      lastRun,
    };
  }

  if (lastRun?.status === "succeeded") {
    return {
      status: "scheduled",
      summary: "CronJob is scheduled and the latest observed run succeeded.",
      lastRun,
    };
  }

  return {
    status: "scheduled",
    summary: "CronJob is scheduled, but no completed job was observed yet.",
    lastRun,
  };
}

function summarizeWorkloadStatus(services: ServiceSnapshot[]): ServiceStatus {
  if (services.some((service) => service.status === "degraded")) {
    return "degraded";
  }

  if (services.some((service) => service.status === "active")) {
    return "active";
  }

  if (services.some((service) => service.status === "scheduled")) {
    return "scheduled";
  }

  if (services.every((service) => service.status === "inactive")) {
    return "inactive";
  }

  return "unknown";
}

async function buildCatalogSnapshot(): Promise<DashboardSnapshot> {
  const workloads = workloadCatalog.map((workload) => {
    const services = workload.services.map(summarizeCatalogService);
    const activeServices = services.filter((service) => service.status === "active").length;

    return {
      ...workload,
      source: "catalog" as const,
      status: summarizeWorkloadStatus(services),
      activeServices,
      totalServices: services.length,
      services,
    };
  });

  return {
    generatedAt: new Date().toISOString(),
    source: "catalog",
    workloads,
  };
}

async function buildClusterSnapshot(kubeConfig: KubeConfig): Promise<DashboardSnapshot> {
  const batchApi = kubeConfig.makeApiClient(BatchV1Api);
  const appsDeploymentApi = kubeConfig.makeApiClient(AppsV1Api);

  const workloads = await Promise.all(
    workloadCatalog.map(async (workload) => {
      const [deploymentResponse, cronJobResponse, jobResponse] = await Promise.all([
        appsDeploymentApi.listNamespacedDeployment({ namespace: workload.namespace }),
        batchApi.listNamespacedCronJob({ namespace: workload.namespace }),
        batchApi.listNamespacedJob({ namespace: workload.namespace }),
      ]);

      const deployments = deploymentResponse.items;
      const cronJobs = cronJobResponse.items;
      const jobs = jobResponse.items;

      const services = workload.services.map((service) => {
        if (service.kind === "cronjob") {
          const cronJob = cronJobs.find((item) => item.metadata?.name === service.cronJobName);
          const relatedJobs = jobs
            .filter((item) => item.metadata?.ownerReferences?.some((owner) => owner.kind === "CronJob" && owner.name === service.cronJobName))
            .sort((left, right) => {
              const leftTime = new Date(
                left.status?.completionTime ?? left.status?.startTime ?? left.metadata?.creationTimestamp ?? 0,
              ).getTime();
              const rightTime = new Date(
                right.status?.completionTime ?? right.status?.startTime ?? right.metadata?.creationTimestamp ?? 0,
              ).getTime();
              return rightTime - leftTime;
            })
            .map((job) => ({
              name: job.metadata?.name,
              status: job.status?.active
                ? { status: "running" as const }
                : job.status?.succeeded
                  ? {
                      status: "succeeded" as const,
                      finishedAt: job.status.completionTime?.toISOString(),
                    }
                  : job.status?.failed
                    ? {
                        status: "failed" as const,
                        finishedAt: job.status.completionTime?.toISOString(),
                      }
                    : { status: "unknown" as const },
            }));

          return {
            ...service,
            ...deriveCronJobStatus(cronJob, getLastRun(relatedJobs)),
            source: "cluster" as const,
          };
        }

        const deployment = deployments.find((item) => item.metadata?.name === service.deploymentName);

        return {
          ...service,
          ...deriveDeploymentStatus(deployment),
          source: "cluster" as const,
        };
      });

      return {
        ...workload,
        source: "cluster" as const,
        status: summarizeWorkloadStatus(services),
        activeServices: services.filter((service) => service.status === "active").length,
        totalServices: services.length,
        services,
      };
    }),
  );

  return {
    generatedAt: new Date().toISOString(),
    source: "cluster",
    workloads,
  };
}

export async function getDashboardSnapshot(): Promise<DashboardSnapshot> {
  try {
    const kubeConfig = getKubeConfigFromEnv();
    if (!kubeConfig) {
      return buildCatalogSnapshot();
    }

    return await buildClusterSnapshot(kubeConfig);
  } catch (error) {
    const snapshot = await buildCatalogSnapshot();
    const reason = error instanceof Error ? error.message : "Unknown cluster read error";

    return {
      ...snapshot,
      workloads: snapshot.workloads.map((workload) => ({
        ...workload,
        services: workload.services.map((service) => ({
          ...service,
          summary: `${service.summary} Cluster read fallback: ${reason}.`,
        })),
      })),
    };
  }
}
