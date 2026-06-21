package connectivity

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/config"
)

type Status struct {
	TailscaledPresent bool
	TailscaledService string
	TailscaledActive  bool
	HasTailscaleIPv4  bool
	K3SService        string
	K3SActive         bool
	Peer              string
	PeerReachable     bool
	PeerCheckSkipped  bool
}

func Inspect(
	ctx context.Context,
	runScript func(context.Context, string) (string, error),
	cfg config.JanitorConfig,
) (Status, error) {
	output, err := runScript(ctx, BuildInspectConnectivityScript(cfg.TailscalePeer, cfg.TailscalePingTimeout))
	if err != nil {
		return Status{}, fmt.Errorf("inspect connectivity: %w", err)
	}

	return ParseStatus(output), nil
}

func ParseStatus(raw string) Status {
	values := map[string]string{}
	for _, line := range strings.Split(raw, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		values[parts[0]] = parts[1]
	}

	return Status{
		TailscaledPresent: values["TAILSCALED_PRESENT"] == "true",
		TailscaledService: values["TAILSCALED_SERVICE"],
		TailscaledActive:  values["TAILSCALED_ACTIVE"] == "true",
		HasTailscaleIPv4:  values["TAILSCALE_HAS_IPV4"] == "true",
		K3SService:        values["K3S_SERVICE"],
		K3SActive:         values["K3S_ACTIVE"] == "true",
		Peer:              values["PEER"],
		PeerReachable:     values["PEER_REACHABLE"] == "true",
		PeerCheckSkipped:  values["PEER_REACHABLE"] == "skip",
	}
}

func BuildSelfHealScript(restartTailscale bool, tailscaledService string, restartK3S bool, k3sService string) string {
	return fmt.Sprintf(`
set -eu

export PATH="/var/lib/rancher/k3s/data/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

restart_tailscale=%q
tailscaled_service=%q
restart_k3s=%q
k3s_service=%q

restart_service() {
  unit="$1"
  if systemctl restart "$unit" 2>/dev/null; then
    return 0
  fi
  if command -v service >/dev/null 2>&1; then
    service "$unit" restart
    return 0
  fi
  return 1
}

if [ "$restart_tailscale" = "true" ] && [ -n "$tailscaled_service" ]; then
  echo "[janitor] restarting $tailscaled_service"
  restart_service "$tailscaled_service"
  sleep 5
fi

if [ "$restart_k3s" = "true" ] && [ -n "$k3s_service" ]; then
  echo "[janitor] restarting $k3s_service"
  restart_service "$k3s_service"
fi
`, strconv.FormatBool(restartTailscale), tailscaledService, strconv.FormatBool(restartK3S), k3sService)
}

func BuildInspectConnectivityScript(peer string, pingTimeout time.Duration) string {
	return fmt.Sprintf(`
set -eu

export PATH="/var/lib/rancher/k3s/data/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

override_peer=%q
ping_timeout=%d

tailscaled_present=false
tailscaled_service=""
tailscaled_active=false
tailscale_has_ipv4=false
k3s_service=""
k3s_active=false
peer=""
peer_reachable=skip

has_systemd_unit() {
  unit="$1"
  if [ "$(systemctl show -p LoadState --value "$unit" 2>/dev/null || true)" = "loaded" ]; then
    return 0
  fi
  [ -f "/etc/systemd/system/$unit.service" ] || \
    [ -f "/lib/systemd/system/$unit.service" ] || \
    [ -f "/usr/lib/systemd/system/$unit.service" ]
}

is_service_active() {
  unit="$1"
  proc_name="$2"
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    return 0
  fi
  pgrep -x "$proc_name" >/dev/null 2>&1
}

if has_systemd_unit snap.tailscale.tailscaled; then
  tailscaled_present=true
  tailscaled_service="snap.tailscale.tailscaled"
elif has_systemd_unit tailscaled || command -v tailscale >/dev/null 2>&1 || command -v tailscaled >/dev/null 2>&1 || pgrep -x tailscaled >/dev/null 2>&1; then
  tailscaled_present=true
  tailscaled_service="tailscaled"
fi

if [ -n "$tailscaled_service" ] && is_service_active "$tailscaled_service" tailscaled; then
    tailscaled_active=true
fi

if [ "$tailscaled_present" = true ]; then
  if tailscale ip -4 >/dev/null 2>&1; then
    tailscale_has_ipv4=true
  fi
fi

if [ -n "$override_peer" ]; then
  peer="$override_peer"
elif pgrep -x k3s-agent >/dev/null 2>&1 && [ -f /etc/systemd/system/k3s-agent.service.env ]; then
  # shellcheck disable=SC1091
  . /etc/systemd/system/k3s-agent.service.env
  peer="${K3S_URL:-}"
  peer="${peer#https://}"
  peer="${peer#http://}"
  peer="${peer%%%%:*}"
fi

if pgrep -x k3s >/dev/null 2>&1 || has_systemd_unit k3s; then
  k3s_service="k3s"
elif pgrep -x k3s-agent >/dev/null 2>&1 || has_systemd_unit k3s-agent || [ -f /etc/systemd/system/k3s-agent.service.env ]; then
  k3s_service="k3s-agent"
fi

if [ -n "$k3s_service" ] && is_service_active "$k3s_service" "$k3s_service"; then
  k3s_active=true
fi

if [ -n "$peer" ] && [ "$tailscaled_present" = true ] && [ "$tailscaled_active" = true ]; then
  if timeout "$ping_timeout" tailscale ping --timeout=5s --c=1 "$peer" >/dev/null 2>&1; then
    peer_reachable=true
  else
    peer_reachable=false
  fi
fi

printf 'TAILSCALED_PRESENT=%%s\n' "$tailscaled_present"
printf 'TAILSCALED_SERVICE=%%s\n' "$tailscaled_service"
printf 'TAILSCALED_ACTIVE=%%s\n' "$tailscaled_active"
printf 'TAILSCALE_HAS_IPV4=%%s\n' "$tailscale_has_ipv4"
printf 'K3S_SERVICE=%%s\n' "$k3s_service"
printf 'K3S_ACTIVE=%%s\n' "$k3s_active"
printf 'PEER=%%s\n' "$peer"
printf 'PEER_REACHABLE=%%s\n' "$peer_reachable"
`, peer, int(pingTimeout.Seconds()))
}
