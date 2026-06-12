# Control Plane Status UI

Read-only status dashboard for `homelab-cloud`, designed for Vercel deployment.

Important boundary:

- this app is Vercel-only
- it is not packaged as a Helm chart
- it must not be deployed to the homelab k3s cluster

## Local Run

```bash
cd apps/client
npm install
npm run dev
```

## Modes

- default: repo-defined catalog mode
- optional: live Kubernetes read-only mode through Vercel env vars

## Vercel Project Setup

Create one Vercel project whose root directory is `apps/client`.

Recommended wiring:

1. In Vercel, create or import a project for this repo.
2. Set the project root directory to `apps/client`.
3. In GitHub repository settings, add:
   - secret: `VERCEL_TOKEN`
   - variable: `VERCEL_ORG_ID`
   - variable: `VERCEL_CONTROL_PLANE_STATUS_PROJECT_ID`
4. Enable the GitHub Actions workflow at `.github/workflows/deploy-client-vercel.yml`.

That workflow deploys production in three cases:

- when `apps/client/**` changes on `main`
- when you run the workflow manually
- when one of the main cluster deploy workflows completes successfully on `main`

### Live Kubernetes Env

Use one of:

- `KUBECONFIG_BASE64`
- `KUBECONFIG_YAML`

When neither is present, the app falls back to chart-defined services and marks them accordingly.

## API

- `GET /api/status`

This route returns the same snapshot used by the homepage.
