"""Evaluation framework for the Customer Service Analyst Agent.

Provides golden dataset, manual review scoring, LLM-as-a-judge templates,
and deterministic evaluation metrics. No LLM API calls are made in this module.
"""
from src.evaluation.golden_dataset import GOLDEN_DATASET, GoldenEntry
from src.evaluation.eval_metrics import compute_pass_rate, compute_route_accuracy, summarize_evaluation

__all__ = [
    "GOLDEN_DATASET",
    "GoldenEntry",
    "compute_pass_rate",
    "compute_route_accuracy",
    "summarize_evaluation",
]
