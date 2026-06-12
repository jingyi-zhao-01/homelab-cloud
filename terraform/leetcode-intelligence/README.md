# LeetCode Intelligence Upstash Runtime

This Terraform root module provisions the Upstash Redis database used for `leetcode-intelligence` non-admin IP rate limiting and writes the runtime values into AWS SSM Parameter Store.

## Scope

- create one Upstash Redis database for Vercel-side rate limiting
- store `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` in SSM
- store the non-admin rate-limit policy values in SSM so the Vercel deploy workflow can sync them into the project environment

## SSM Parameters

By default this stack writes:

- `/leetcode-intelligence/UPSTASH_REDIS_REST_URL`
- `/leetcode-intelligence/UPSTASH_REDIS_REST_TOKEN`
- `/leetcode-intelligence/NON_ADMIN_RATE_LIMIT_MAX_REQUESTS`
- `/leetcode-intelligence/NON_ADMIN_RATE_LIMIT_WINDOW_SECONDS`

It also expects the Upstash provider bootstrap credentials to already exist in SSM:

- `/upstash/email`
- `/upstash/api_key`

## Example

```bash
cd terraform/leetcode-intelligence
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="key=leetcode-intelligence/upstash/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="encrypt=true"
terraform plan
terraform apply
```

## GitHub Actions

This stack is wired to:

- `.github/workflows/terraform-leetcode-intelligence-upstash.yml`

Behavior:

- push to `main` touching `terraform/leetcode-intelligence/**` triggers automatic `terraform apply`
- `workflow_dispatch` supports `plan`, `apply`, and `destroy`

Required GitHub configuration:

- Secret: `AWS_ACCESS_KEY_ID`
- Secret: `AWS_SECRET_ACCESS_KEY`
- Secret: `TF_STATE_BUCKET`
- Variable: `AWS_REGION`

Optional GitHub configuration:

- Variable: `LEETCODE_INTELLIGENCE_UPSTASH_SSM_PATH_PREFIX`
- Variable: `LEETCODE_INTELLIGENCE_UPSTASH_DATABASE_NAME`
- Variable: `LEETCODE_INTELLIGENCE_UPSTASH_PRIMARY_REGION`
- Variable: `LEETCODE_INTELLIGENCE_NON_ADMIN_RATE_LIMIT_MAX_REQUESTS`
- Variable: `LEETCODE_INTELLIGENCE_NON_ADMIN_RATE_LIMIT_WINDOW_SECONDS`
