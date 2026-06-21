# node-disk-janitor

`node-disk-janitor` is a small Go daemon for Kubernetes clusters with tight
node disks.

It is intended to run as a privileged `DaemonSet` on both worker and
control-plane nodes. Each pod:

- measures host root filesystem usage through a host mount
- can self-heal host Tailscale and `k3s`/`k3s-agent` when a node drops off the tailnet
- can garbage-collect finished `Job` objects cluster-wide
- can delete old empty namespaces outside a protected allowlist
- triggers cleanup when usage crosses a configured threshold
- deletes terminated pod objects scheduled to the same node
- enters the host namespaces with `nsenter`, then `chroot`s into the host rootfs to run bounded cleanup and health-check commands

## Default cleanup behavior

The built-in host cleanup command currently tries to:

- vacuum systemd journal history to `2d`
- remove exited CRI containers and dead sandboxes
- prune unused CRI / containerd images
- clean `apt` cache if available

The command is configurable through `HOST_CLEANUP_COMMAND`.

## Required Kubernetes privileges

The daemon needs:

- `list/get/delete` on pods
- `get/list/watch` on nodes
- `list/get/delete` on jobs and namespaces
- `list/get/watch` on services, PVCs, deployments, statefulsets, daemonsets, replicasets, and cronjobs
- privileged container access with `hostPID: true`
- a host root mount at `/host`

## Important env vars

- `NODE_NAME`
- `CHECK_INTERVAL_SECONDS`
- `CLEANUP_COOLDOWN_SECONDS`
- `CLUSTER_CLEANUP_COOLDOWN_SECONDS`
- `TAILSCALE_SELF_HEAL_ENABLED`
- `SELF_HEAL_COOLDOWN_SECONDS`
- `TAILSCALE_PING_TIMEOUT_SECONDS`
- `TAILSCALE_PING_PEER`
- `RESTART_K3S_ON_TAILSCALE_HEAL`
- `DISK_USAGE_TRIGGER_PERCENT`
- `DISK_USAGE_TARGET_PERCENT`
- `DELETE_TERMINATED_PODS`
- `TERMINATED_POD_GRACE_SECONDS`
- `DELETE_FINISHED_JOBS`
- `FINISHED_JOB_GRACE_SECONDS`
- `DELETE_EMPTY_NAMESPACES`
- `EMPTY_NAMESPACE_GRACE_SECONDS`
- `EMPTY_NAMESPACE_PROTECTED_NAMESPACES`
- `HOST_CLEANUP_COMMAND`
