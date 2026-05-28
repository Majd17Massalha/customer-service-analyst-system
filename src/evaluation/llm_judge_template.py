"""LLM-as-a-Judge evaluation template.

Defines evaluation criteria and reusable prompt templates for advisory
LLM-based assessment of agent responses. This module does NOT make any
API calls — it produces template strings that a human or external LLM
runner may use.

IMPORTANT CONSTRAINTS
---------------------
- LLM judge outputs are advisory only.
- Deterministic tool outputs (DuckDB counts, row counts) are the source
  of truth. The LLM judge must never override or dispute exact numeric
  results from verified tools.
- Counts and statistics must never be judged semantically. If the tool
  returns 1,234 rows, that answer is correct regardless of what the
  LLM judge thinks is plausible.
- Judge output should be used to flag suspected issues for human review,
  not to automatically override tool results.
"""
from __future__ import annotations


EVALUATION_DIMENSIONS = {
    "groundedness": (
        "Is every factual claim in the response directly supported by the "
        "tool's output? A response is NOT grounded if it adds information "
        "not present in the observation field."
    ),
    "scope_adherence": (
        "Does the response stay within the Bitext Customer Support dataset "
        "domain? Responses about sports, finance, weather, or general world "
        "knowledge violate scope."
    ),
    "hallucination_detection": (
        "Does the response invent data, categories, or intents not present "
        "in the observation? Invented counts or fabricated examples are "
        "hallucinations."
    ),
    "refusal_correctness": (
        "For out-of-scope queries: does the agent refuse without providing "
        "partial in-scope information? A partial answer on an out-of-scope "
        "query is a refusal failure."
    ),
    "summary_quality": (
        "For unstructured queries: is the extractive summary well-formatted, "
        "clearly attributed to dataset examples, and free of invented text? "
        "Note: LLM-generated narratives are NOT used — all summaries are "
        "extractive. Judge should verify the prefix 'Based on dataset examples only:' "
        "is present."
    ),
    "consistency": (
        "Does the response contradict itself or contradict the observation? "
        "E.g., if the tool returns 0, the response must not say 'many rows'."
    ),
}

JUDGE_SYSTEM_PROMPT = """\
You are an evaluation assistant for an AI analytics agent. Your role is
advisory only. You do not have authority to override deterministic tool
outputs. Your evaluations flag suspected issues for human review.

Rules you must follow:
1. NEVER dispute exact numerical results from DuckDB tools. If the agent
   says "1,234 rows", evaluate whether this is correctly attributed to
   the tool — do not judge whether the number seems plausible.
2. NEVER evaluate ungrounded text as "acceptable" if it is not present
   in the observation.
3. For out-of-scope queries, the only acceptable behavior is a clear
   refusal. Partial answers are failures.
4. Mark your output as ADVISORY. A human reviewer makes the final call.
"""

JUDGE_EVALUATION_PROMPT_TEMPLATE = """\
=== Advisory Evaluation Request ===

Query: {query}
Expected route: {expected_route}
Expected tool: {expected_tool}
Expected behavior: {expected_behavior}

Agent response:
  route       : {actual_route}
  tool        : {actual_tool}
  tool_input  : {actual_tool_input}
  observation : {actual_observation}
  final_answer: {actual_final_answer}

Evaluation dimensions (answer each with PASS / FAIL / UNCERTAIN + one sentence):

1. Groundedness
   Is every claim in final_answer directly supported by the observation?
   Answer: [PASS / FAIL / UNCERTAIN] — [reason]

2. Scope adherence
   Does the response stay within the Bitext dataset domain?
   Answer: [PASS / FAIL / UNCERTAIN] — [reason]

3. Hallucination detection
   Does the final_answer invent any data not in the observation?
   Answer: [PASS / FAIL / UNCERTAIN] — [reason]

4. Refusal correctness (if expected_route = out_of_scope)
   Did the agent refuse without leaking any dataset information?
   Answer: [PASS / FAIL / UNCERTAIN / N/A] — [reason]

5. Summary quality (if expected_route = unstructured)
   Is the extractive summary well-formatted and attributed?
   Answer: [PASS / FAIL / UNCERTAIN / N/A] — [reason]

6. Consistency
   Does the response contradict itself or contradict the observation?
   Answer: [PASS / FAIL / UNCERTAIN] — [reason]

Overall advisory verdict: [PASS / FAIL / UNCERTAIN]
One-line reason: [reason]

REMINDER: This evaluation is advisory. Numerical results from DuckDB
are authoritative. A human reviewer must make the final pass/fail decision.
"""


def build_judge_prompt(
    entry_data: dict,
    actual_route: str,
    actual_tool: str | None,
    actual_tool_input: dict,
    actual_observation: object,
    actual_final_answer: str,
) -> str:
    """Build a populated LLM judge prompt string.

    Does not call any API. Returns a string to be sent to an LLM by
    external tooling or a human reviewer using a chat interface.
    """
    return JUDGE_EVALUATION_PROMPT_TEMPLATE.format(
        query=entry_data.get("query", ""),
        expected_route=entry_data.get("expected_route", ""),
        expected_tool=entry_data.get("expected_tool", ""),
        expected_behavior=entry_data.get("expected_behavior", ""),
        actual_route=actual_route,
        actual_tool=actual_tool or "(none)",
        actual_tool_input=actual_tool_input,
        actual_observation=str(actual_observation)[:500],
        actual_final_answer=actual_final_answer,
    )


def get_dimension_description(dimension: str) -> str:
    """Return the evaluation criterion description for a named dimension."""
    if dimension not in EVALUATION_DIMENSIONS:
        raise ValueError(
            f"Unknown dimension {dimension!r}. "
            f"Valid: {list(EVALUATION_DIMENSIONS)}"
        )
    return EVALUATION_DIMENSIONS[dimension]
