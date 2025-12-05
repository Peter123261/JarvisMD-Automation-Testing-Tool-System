#!/usr/bin/env bash
set -euo pipefail

timestamp="$(date +%Y%m%d_%H%M%S)"
out="monitoring_backup_${timestamp}.tar.gz"

tar -czf "$out" \
  monitoring/prometheus.yml \
  monitoring/alert_rules.yml \
  monitoring/alertmanager.yml \
  monitoring/recording_rules.yml \
  monitoring/grafana/provisioning/datasources \
  monitoring/grafana/provisioning/dashboards \
  monitoring/grafana/dashboards

echo "Backup created: $out"


