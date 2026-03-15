"""
Alert generator for incident-triage-agent.

Usage:
    python generator.py --scenario 1|2|3
    python generator.py           # random scenario
"""

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "current.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scenario_1_noise() -> dict:
    """CPU 87%, memoria 72%, latencia +40% — batch de backup nocturno recurrente."""
    return {
        "scenario": 1,
        "timestamp": now_iso(),
        "service": "payments-api",
        "environment": "production",
        "context": {
            "note": "Backup nocturno programado — se ejecuta diariamente 02:00–03:30 UTC",
            "last_deploy": "2026-03-14T16:45:00Z",
            "recurring_pattern": True,
            "pattern_observed_days": 47,
        },
        "metrics": {
            "cpu_percent": 87.2,
            "memory_percent": 72.4,
            "latency_p50_ms": 145,
            "latency_p95_ms": 380,
            "latency_p99_ms": 610,
            "latency_delta_percent": 40,
            "error_rate_percent": 0.12,
            "requests_per_second": 23,
            "requests_per_second_baseline": 280,
            "db_connections_active": 18,
            "db_connections_max": 200,
            "disk_io_mbps": 340,
            "disk_io_baseline_mbps": 45,
        },
        "active_jobs": [
            {
                "name": "nightly-backup",
                "started_at": "2026-03-15T02:00:00Z",
                "status": "running",
                "cpu_affinity": "high",
            }
        ],
    }


def scenario_2_incident() -> dict:
    """CPU 94%, error rate 8.3%, latencia p99 x4, conexiones DB agotándose — cascada."""
    return {
        "scenario": 2,
        "timestamp": now_iso(),
        "service": "payments-api",
        "environment": "production",
        "context": {
            "note": "Sin deploys recientes, sin batch jobs activos, tráfico normal",
            "last_deploy": "2026-03-14T09:20:00Z",
            "recurring_pattern": False,
            "alert_started": "2026-03-15T14:38:00Z",
        },
        "metrics": {
            "cpu_percent": 94.1,
            "memory_percent": 88.7,
            "latency_p50_ms": 890,
            "latency_p95_ms": 3200,
            "latency_p99_ms": 8400,
            "latency_p99_baseline_ms": 2100,
            "latency_delta_percent": 300,
            "error_rate_percent": 8.3,
            "error_rate_baseline_percent": 0.15,
            "requests_per_second": 310,
            "requests_per_second_baseline": 290,
            "db_connections_active": 198,
            "db_connections_max": 200,
            "db_connection_wait_ms": 4500,
            "db_query_timeout_count_last_5min": 847,
            "http_5xx_count_last_5min": 1203,
            "http_5xx_baseline_per_5min": 22,
        },
        "active_jobs": [],
        "downstream_services": {
            "fraud-detection": {"status": "degraded", "latency_p99_ms": 5100},
            "notification-service": {"status": "healthy", "latency_p99_ms": 180},
        },
    }


def scenario_3_ambiguous() -> dict:
    """CPU 78%, latencia p95 +65%, error rate 1.2% — post-deploy hace 20 min."""
    return {
        "scenario": 3,
        "timestamp": now_iso(),
        "service": "payments-api",
        "environment": "production",
        "context": {
            "note": "Deploy hace 20 minutos — dentro de la ventana de observación post-deploy",
            "last_deploy": "2026-03-15T14:05:00Z",
            "deploy_version": "v2.14.3",
            "deploy_previous_version": "v2.14.2",
            "recurring_pattern": False,
            "canary_traffic_percent": 100,
        },
        "metrics": {
            "cpu_percent": 78.3,
            "memory_percent": 61.2,
            "latency_p50_ms": 210,
            "latency_p50_baseline_ms": 130,
            "latency_p95_ms": 820,
            "latency_p95_baseline_ms": 495,
            "latency_delta_percent": 65,
            "latency_p99_ms": 1900,
            "latency_p99_baseline_ms": 1850,
            "error_rate_percent": 1.2,
            "error_rate_baseline_percent": 0.15,
            "requests_per_second": 295,
            "requests_per_second_baseline": 285,
            "db_connections_active": 74,
            "db_connections_max": 200,
            "http_4xx_count_last_5min": 38,
            "http_5xx_count_last_5min": 61,
            "http_5xx_baseline_per_5min": 22,
        },
        "active_jobs": [],
        "trend": {
            "latency_p95_direction": "stable",
            "error_rate_direction": "stable",
            "note": "Métricas elevadas pero sin tendencia de empeoramiento en los últimos 5 min",
        },
    }


SCENARIOS = {
    1: scenario_1_noise,
    2: scenario_2_incident,
    3: scenario_3_ambiguous,
}


def main():
    parser = argparse.ArgumentParser(description="Generate alert scenarios for incident-triage-agent")
    parser.add_argument(
        "--scenario",
        type=int,
        choices=[1, 2, 3],
        help="Scenario to generate (1=noise, 2=incident, 3=ambiguous). Random if omitted.",
    )
    args = parser.parse_args()

    scenario_id = args.scenario if args.scenario else random.choice([1, 2, 3])
    alert = SCENARIOS[scenario_id]()

    OUTPUT_PATH.write_text(json.dumps(alert, indent=2))

    labels = {1: "ruido (batch nocturno)", 2: "incidente real (cascada)", 3: "ambiguo (post-deploy)"}
    print(f"Escenario {scenario_id} generado: {labels[scenario_id]}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
