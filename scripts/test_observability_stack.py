from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    compose_path = ROOT / "docker-compose.observability.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    required_services = {
        "otel-collector",
        "prometheus",
        "tempo",
        "loki",
        "alloy",
        "grafana",
    }
    services = compose.get("services", {})
    assert required_services <= services.keys()

    for service_name in required_services:
        image = str(services[service_name].get("image", ""))
        assert image and not image.endswith(":latest"), (
            f"{service_name} must use a fixed image version"
        )

    yaml_configs = [
        ROOT / "monitoring" / "otel-collector" / "config.yaml",
        ROOT / "monitoring" / "prometheus" / "prometheus.yml",
        ROOT / "monitoring" / "prometheus" / "alerts.yml",
        ROOT / "monitoring" / "tempo" / "tempo.yaml",
        ROOT / "monitoring" / "loki" / "loki.yaml",
        ROOT
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "datasources"
        / "datasources.yaml",
    ]
    for config_path in yaml_configs:
        assert yaml.safe_load(config_path.read_text(encoding="utf-8"))

    dashboard_dir = ROOT / "monitoring" / "grafana" / "dashboards"
    dashboards = list(dashboard_dir.glob("*.json"))
    assert len(dashboards) >= 3
    for dashboard_path in dashboards:
        payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
        assert payload.get("uid")
        assert payload.get("title")
        assert payload.get("panels")

    print("Observability stack static validation passed")


if __name__ == "__main__":
    main()
