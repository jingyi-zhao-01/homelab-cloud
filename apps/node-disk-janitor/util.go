package main

import (
	"log"
	"os"
	"strconv"
	"strings"
	"time"
)

func mustDurationEnv(name string, fallback time.Duration) time.Duration {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	seconds, err := strconv.Atoi(raw)
	if err != nil || seconds <= 0 {
		log.Fatalf("%s must be a positive integer number of seconds, got %q", name, raw)
	}
	return time.Duration(seconds) * time.Second
}

func mustPercentEnv(name string, fallback float64) float64 {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	value, err := strconv.ParseFloat(raw, 64)
	if err != nil || value <= 0 || value >= 100 {
		log.Fatalf("%s must be a percentage between 0 and 100, got %q", name, raw)
	}
	return value
}

func mustBoolEnv(name string, fallback bool) bool {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	switch strings.ToLower(raw) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		log.Fatalf("%s must be a boolean, got %q", name, raw)
		return false
	}
}

func getenvDefault(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func parseCSVEnv(name string, fallback []string) []string {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}

	parts := strings.Split(raw, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed == "" {
			continue
		}
		values = append(values, trimmed)
	}
	if len(values) == 0 {
		return fallback
	}
	return values
}

func defaultProtectedNamespaces() []string {
	return []string{
		"default",
		"kube-node-lease",
		"kube-public",
		"kube-system",
		"control-plane-agents",
		"datadog",
		"monitoring",
	}
}
