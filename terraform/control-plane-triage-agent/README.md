# Control Plane Triage Agent Resources

This Terraform root module provisions the namespaced AWS SSM parameter consumed by the `control-plane-triage-agent` chart for OpenHands/OpenRouter-backed diagnosis.

## Scope

- read one source OpenRouter API key from AWS SSM or a direct Terraform variable
- write the namespaced runtime secret consumed by the control-plane triage agent

## SSM Parameters

By default this stack writes:

- `/control-plane-triage-agent/prod/OPENHANDS_LLM_API_KEY`

By default it expects the source key to already exist at:

- `/openrouter/OPEN_ROUTER_API_KEY`

Important: Terraform cannot mint a new OpenRouter API key for you. It can only copy/sync a key you already created into the service-specific SSM path.

## Example

```bash
cd terraform/control-plane-triage-agent
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="key=control-plane-triage-agent/resources/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="encrypt=true"
terraform plan
terraform apply
```

## GitHub Actions

This stack is wired to:

- `.github/workflows/terraform-control-plane-triage-agent-resources.yml`
