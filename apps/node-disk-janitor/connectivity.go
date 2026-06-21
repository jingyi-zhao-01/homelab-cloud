package main

import (
	"context"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"
)

func (j *janitor) ensureNodeConnectivity(ctx context.Context) error {
	status, err := j.inspectConnectivity(ctx)
	if err != nil {
		return err
	}

	if !status.tailscaledPresent {
		log.Printf("node=%s tailscale self-heal skipped: tailscaled service not present", j.cfg.nodeName)
		return nil
	}

	if status.tailscaledActive && status.hasTailscaleIPv4 && (status.peerCheckSkipped || status.peerReachable) && (status.k3sService == "" || status.k3sActive) {
		return nil
	}

	if time.Since(j.lastSelfHealTime) < j.cfg.selfHealCooldown {
		log.Printf(
			"node=%s self-heal suppressed by cooldown remaining=%s tailscaled_active=%t tailscale_ip=%t peer=%q peer_reachable=%t k3s_service=%q k3s_active=%t",
			j.cfg.nodeName,
			j.cfg.selfHealCooldown-time.Since(j.lastSelfHealTime),
			status.tailscaledActive,
			status.hasTailscaleIPv4,
			status.peer,
			status.peerReachable,
			status.k3sService,
			status.k3sActive,
		)
		return nil
	}

	j.lastSelfHealTime = time.Now()

	log.Printf(
		"node=%s starting self-heal tailscaled_active=%t tailscale_ip=%t peer=%q peer_reachable=%t k3s_service=%q k3s_active=%t",
		j.cfg.nodeName,
		status.tailscaledActive,
		status.hasTailscaleIPv4,
		status.peer,
		status.peerReachable,
		status.k3sService,
		status.k3sActive,
	)

	needsTailscaleRestart := !status.tailscaledActive || !status.hasTailscaleIPv4 || (!status.peerCheckSkipped && !status.peerReachable)
	needsK3SRestart := (status.k3sService != "" && !status.k3sActive) || (needsTailscaleRestart && j.cfg.restartK3SOnHeal && status.k3sService != "")

	output, err := j.runHostScript(ctx, buildSelfHealScript(needsTailscaleRestart, needsK3SRestart, status.k3sService))
	if strings.TrimSpace(output) != "" {
		log.Printf("node=%s self-heal output:\n%s", j.cfg.nodeName, output)
	}
	if err != nil {
		return err
	}

	return nil
}

func (j *janitor) inspectConnectivity(ctx context.Context) (connectivityStatus, error) {
	output, err := j.runHostScript(ctx, j.inspectConnectivityScript())
	if err != nil {
		return connectivityStatus{}, fmt.Errorf("inspect connectivity: %w", err)
	}

	values := map[string]string{}
	for _, line := range strings.Split(output, "\n") {
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

	return connectivityStatus{
		tailscaledPresent: values["TAILSCALED_PRESENT"] == "true",
		tailscaledActive:  values["TAILSCALED_ACTIVE"] == "true",
		hasTailscaleIPv4:  values["TAILSCALE_HAS_IPV4"] == "true",
		k3sService:        values["K3S_SERVICE"],
		k3sActive:         values["K3S_ACTIVE"] == "true",
		peer:              values["PEER"],
		peerReachable:     values["PEER_REACHABLE"] == "true",
		peerCheckSkipped:  values["PEER_REACHABLE"] == "skip",
	}, nil
}

func (j *janitor) inspectConnectivityScript() string {
	return fmt.Sprintf(`
set -eu

export PATH="/var/lib/rancher/k3s/data/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

override_peer=%q
ping_timeout=%d

tailscaled_present=false
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

if has_systemd_unit tailscaled || command -v tailscale >/dev/null 2>&1 || command -v tailscaled >/dev/null 2>&1 || pgrep -x tailscaled >/dev/null 2>&1; then
  tailscaled_present=true
  if is_service_active tailscaled tailscaled; then
    tailscaled_active=true
  fi
  if tailscale ip -4 >/dev/null 2>&1; then
    tailscale_has_ipv4=true
  fi
fi

if [ -n "$override_peer" ]; then
  peer="$override_peer"
elif [ -f /etc/systemd/system/k3s-agent.service.env ]; then
  # shellcheck disable=SC1091
  . /etc/systemd/system/k3s-agent.service.env
  peer="${K3S_URL:-}"
  peer="${peer#https://}"
  peer="${peer#http://}"
  peer="${peer%%%%:*}"
fi

if has_systemd_unit k3s-agent || [ -f /etc/systemd/system/k3s-agent.service.env ] || pgrep -x k3s-agent >/dev/null 2>&1; then
  k3s_service="k3s-agent"
elif has_systemd_unit k3s || pgrep -x k3s >/dev/null 2>&1; then
  k3s_service="k3s"
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
printf 'TAILSCALED_ACTIVE=%%s\n' "$tailscaled_active"
printf 'TAILSCALE_HAS_IPV4=%%s\n' "$tailscale_has_ipv4"
printf 'K3S_SERVICE=%%s\n' "$k3s_service"
printf 'K3S_ACTIVE=%%s\n' "$k3s_active"
printf 'PEER=%%s\n' "$peer"
printf 'PEER_REACHABLE=%%s\n' "$peer_reachable"
`, j.cfg.tailscalePeer, int(j.cfg.tailscalePingTimeout.Seconds()))
}

func buildSelfHealScript(restartTailscale, restartK3S bool, k3sService string) string {
	return fmt.Sprintf(`
set -eu

export PATH="/var/lib/rancher/k3s/data/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

restart_tailscale=%q
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

if [ "$restart_tailscale" = "true" ]; then
  echo "[janitor] restarting tailscaled"
  restart_service tailscaled
  sleep 5
fi

if [ "$restart_k3s" = "true" ] && [ -n "$k3s_service" ]; then
  echo "[janitor] restarting $k3s_service"
  restart_service "$k3s_service"
fi
`, strconv.FormatBool(restartTailscale), strconv.FormatBool(restartK3S), k3sService)
}
