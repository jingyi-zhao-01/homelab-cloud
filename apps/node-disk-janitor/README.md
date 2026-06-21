# node-disk-janitor

`node-disk-janitor` is a small Go daemon for Kubernetes clusters with tight
node disks.

It is intended to run as a privileged `DaemonSet` on both worker and
control-plane nodes. Each pod:

- measures host root filesystem usage through a host mount
- triggers cleanup when usage crosses a configured threshold
- deletes terminated pod objects scheduled to the same node
- enters the host namespaces with `nsenter` and runs a bounded cleanup command

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
- privileged container access with `hostPID: true`
- a host root mount at `/host`

## Important env vars

- `NODE_NAME`
- `CHECK_INTERVAL_SECONDS`
- `CLEANUP_COOLDOWN_SECONDS`
- `DISK_USAGE_TRIGGER_PERCENT`
- `DISK_USAGE_TARGET_PERCENT`
- `DELETE_TERMINATED_PODS`
- `TERMINATED_POD_GRACE_SECONDS`
- `HOST_CLEANUP_COMMAND`
