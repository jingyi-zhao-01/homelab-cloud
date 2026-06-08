import { type ServiceStatus, type WorkloadSnapshot } from "@/lib/catalog";
import { getDashboardSnapshot } from "@/lib/status";

const statusClassName: Record<ServiceStatus, string> = {
  active: "status-active",
  degraded: "status-degraded",
  inactive: "status-inactive",
  scheduled: "status-scheduled",
  unknown: "status-unknown",
};

function getStatusClassName(status: ServiceStatus) {
  return statusClassName[status];
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function describeMode(source: "catalog" | "cluster") {
  return source === "cluster"
    ? "Live cluster read-only mode"
    : "Repo-defined fallback mode";
}

function ServiceCard({ workload }: { workload: WorkloadSnapshot }) {
  return (
    <article className="card workload-card">
      <div className="workload-header">
        <div>
          <h2>{workload.name}</h2>
          <p>{workload.description}</p>
        </div>
        <span className={`status-badge ${getStatusClassName(workload.status)}`}>
          <span className="dot" />
          {workload.status}
        </span>
      </div>

      <ul className="workload-meta">
        <li className="pill">Namespace: {workload.namespace}</li>
        <li className="pill">
          Active now: {workload.activeServices}/{workload.totalServices}
        </li>
        <li className="pill">Source: {describeMode(workload.source)}</li>
      </ul>

      <div className="service-list">
        {workload.services.map((service: WorkloadSnapshot["services"][number]) => (
          <section className="service-row" key={service.id}>
            <header>
              <div>
                <h3>{service.name}</h3>
              </div>
              <span className={`status-badge ${getStatusClassName(service.status)}`}>
                <span className="dot" />
                {service.status}
              </span>
            </header>
            <p>{service.description}</p>
            <ul className="service-meta">
              <li className="pill">Kind: {service.kind}</li>
              {service.deploymentName ? <li className="pill">Deployment: {service.deploymentName}</li> : null}
              {service.cronJobName ? <li className="pill">CronJob: {service.cronJobName}</li> : null}
              {typeof service.desiredReplicas === "number" ? (
                <li className="pill">
                  Replicas: {service.availableReplicas ?? 0}/{service.desiredReplicas}
                </li>
              ) : null}
              {service.lastRun ? (
                <li className="pill">
                  Last run: {service.lastRun.status}
                  {service.lastRun.finishedAt ? ` at ${formatTimestamp(service.lastRun.finishedAt)}` : ""}
                </li>
              ) : null}
            </ul>
            <p className="meta">{service.summary}</p>
          </section>
        ))}
      </div>
    </article>
  );
}

export default async function Page() {
  const snapshot = await getDashboardSnapshot();
  const totalServices = snapshot.workloads.reduce((sum, workload) => sum + workload.totalServices, 0);
  const activeServices = snapshot.workloads.reduce((sum, workload) => sum + workload.activeServices, 0);
  const scheduledServices = snapshot.workloads.reduce(
    (sum, workload) => sum + workload.services.filter((service) => service.status === "scheduled").length,
    0,
  );
  const degradedWorkloads = snapshot.workloads.filter((workload) => workload.status === "degraded").length;

  return (
    <main className="shell">
      <section className="hero">
        <span className="eyebrow">homelab cloud control plane status</span>
        <h1>Read what is alive without opening kubectl.</h1>
        <p>
          This UI is intentionally read-only. It presents the workloads this repo owns, the services they define, and
          optional live cluster status when Vercel has kubeconfig access.
        </p>

        <div className="summary-grid">
          <div className="panel metric">
            <span className="metric-label">Status source</span>
            <strong>{describeMode(snapshot.source)}</strong>
            <span>{snapshot.source === "cluster" ? "Backed by Kubernetes API" : "Backed by chart catalog only"}</span>
          </div>
          <div className="panel metric">
            <span className="metric-label">Workloads</span>
            <strong>{snapshot.workloads.length}</strong>
            <span>Flashsales, LeetCode Intelligence, and Strategy Tester</span>
          </div>
          <div className="panel metric">
            <span className="metric-label">Services active</span>
            <strong>
              {activeServices}/{totalServices}
            </strong>
            <span>Only running Deployments and active workers count here</span>
          </div>
          <div className="panel metric">
            <span className="metric-label">Cron health</span>
            <strong>{scheduledServices}</strong>
            <span>{degradedWorkloads} workload(s) currently flagged as degraded</span>
          </div>
        </div>

        <div className="hero-grid">
          <section className="panel">
            <h2>How this version thinks</h2>
            <p className="section-copy">
              Deployments and workers are shown as active only when the Kubernetes API reports available replicas. Cron
              workloads stay visible and keep their own last-run state instead of being flattened into fake services.
            </p>
          </section>
          <section className="panel">
            <h2>Last refresh</h2>
            <p className="section-copy">{formatTimestamp(snapshot.generatedAt)}</p>
            <p className="section-copy">
              API route: <code>/api/status</code>
            </p>
          </section>
        </div>
      </section>

      <section>
        <div className="section-heading">
          <div>
            <h2>Workload View</h2>
            <p className="section-copy">
              Service cards map directly to the repo&apos;s Helm charts, so the UI stays aligned with the deploy surface.
            </p>
          </div>
          <div className="timestamp">Updated {formatTimestamp(snapshot.generatedAt)}</div>
        </div>

        <div className="workload-grid">
          {snapshot.workloads.map((workload) => (
            <ServiceCard key={workload.id} workload={workload} />
          ))}
        </div>
      </section>

      <section className="footer-grid">
        <article className="footer-card">
          <h3>Vercel env you can wire next</h3>
          <ul>
            <li>`KUBECONFIG_BASE64` for live cluster reads from a base64 kubeconfig</li>
            <li>`KUBECONFIG_YAML` if you prefer plain kubeconfig text instead</li>
            <li>No write flows are implemented in this app</li>
          </ul>
        </article>
        <article className="footer-card">
          <h3>What this intentionally skips</h3>
          <p>
            No job triggers, no deploy buttons, no Helm mutation, and no pipeline controls. This stays read-only and
            so the UI is safe to host separately on Vercel.
          </p>
        </article>
      </section>
    </main>
  );
}
