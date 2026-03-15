# Incident Triage Agent

Multi-agent incident triage built with Claude Code. An orchestrator coordinates two specialized agents — Analyst and Responder — with conditional execution based on SRE criteria, not just thresholds.

## How it works

1. `generator.py` produces `alerts/current.json` with realistic fake metrics
2. The orchestrator reads `CLAUDE.md` and invokes the **Analyst** agent
3. Analyst correlates signals and writes a structured decision to `output/analysis.json`
4. If `incident: true` → **Responder** generates a runbook in `output/runbook.md`
5. If `incident: false` → flow stops with justification. No runbook, no noise.

The Analyst requires ≥2 correlated signals before declaring an incident. A single metric over threshold is not enough.

## Run it

Generate a scenario (1=noise, 2=real incident, 3=ambiguous):

    python alerts/generator.py --scenario 2

Launch the orchestrator inside Claude Code:

    run @CLAUDE.md

## Scenarios

| Scenario | Description | Expected decision |
|----------|-------------|-------------------|
| 1 | High CPU + disk I/O — recurring backup batch at 02:00 | `incident: false` |
| 2 | DB connection pool exhausted, cascading failure | `incident: true / critical` |
| 3 | Post-deploy latency spike, ambiguous correlation | `watch and wait` |

## Why this exists

Built as a practical experiment on multi-agent orchestration with Claude Code. The goal: an agent that reasons about causality, not one that fires on thresholds.

Full write-up → link

## Stack

- Claude Code (orchestrator + agents via CLAUDE.md)
- Python
