"""Prometheus metrics.

Traces are per run and metrics are per fleet. An alert cannot watch a
trace, which is why Beat 10.4's "refund value per hour" needs these.

Rates are not stored. Escalation rate is escalate runs over all runs, and
Prometheus computes that from the labelled counter. Storing a rate would
mean storing a number that is already wrong by the time it is read.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

from ops_agent.config import settings

RUNS = Counter(
    "ops_agent_runs_total",
    "Agent runs, labelled by the decision they reached.",
    ["decision"],
)

REFUND_VALUE = Counter(
    "ops_agent_refund_value_minor_total",
    "Money refunded, in minor units. The number an alert watches.",
)

LATENCY = Histogram(
    "ops_agent_run_latency_seconds",
    "Wall clock time for one /chat request.",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60),
)

STEPS = Histogram(
    "ops_agent_steps_per_run",
    "Model calls in one run. The step limit is 8, so a run near it is a loop.",
    buckets=(1, 2, 3, 4, 5, 6, 7, 8),
)

COST = Counter(
    "ops_agent_cost_inr_total",
    "Gateway spend in rupees. Credits are a real cost.",
)

TOOL_REFUSALS = Counter(
    "ops_agent_tool_refusals_total",
    "Tool calls refused by the tool layer, labelled by refusal code.",
    ["code"],
)


def cost_inr(input_tokens: int, output_tokens: int) -> float:
    """Pinned rates from config, so a recorded cost is reproducible."""
    return round(
        input_tokens * settings.llm_input_inr_per_million / 1_000_000
        + output_tokens * settings.llm_output_inr_per_million / 1_000_000,
        4,
    )
