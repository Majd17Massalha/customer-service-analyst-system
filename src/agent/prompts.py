"""Few-shot routing examples for the Customer Service Analyst Agent.

These examples define expected routing behavior and serve two purposes:
1. Ground-truth test cases for the deterministic router.
2. Few-shot examples for LLM-assisted routing (future task).

No LLM calls are made here.
"""
from __future__ import annotations

FEW_SHOT_EXAMPLES: list[dict[str, str]] = [
    # structured — counting, filtering, distribution
    {"query": "How many refund requests are in the dataset?", "route": "structured"},
    {"query": "What categories exist in the dataset?", "route": "structured"},
    {"query": "What is the distribution of intents in the ACCOUNT category?", "route": "structured"},
    {"query": "What is the total number of rows?", "route": "structured"},
    {"query": "How many rows belong to the FEEDBACK category?", "route": "structured"},
    {"query": "What are the top 5 intents by frequency?", "route": "structured"},
    # unstructured — summarization, open-ended explanation
    {"query": "Summarize the FEEDBACK category.", "route": "unstructured"},
    {"query": "How do agents respond to cancellation requests?", "route": "unstructured"},
    {"query": "Tell me about the ACCOUNT category.", "route": "unstructured"},
    {"query": "Give me an overview of the dataset.", "route": "unstructured"},
    {"query": "Explain the intent patterns in the support data.", "route": "unstructured"},
    {"query": "What are the common issues in the REFUND category?", "route": "unstructured"},
    # out_of_scope — unrelated to Bitext dataset
    {"query": "Who won the Champions League?", "route": "out_of_scope"},
    {"query": "Write me a poem about customer service.", "route": "out_of_scope"},
    {"query": "What is the weather in New York?", "route": "out_of_scope"},
    {"query": "Tell me a joke.", "route": "out_of_scope"},
    {"query": "What is the stock price of Apple?", "route": "out_of_scope"},
    # needs_clarification — ambiguous or context-dependent
    {"query": "Show me more", "route": "needs_clarification"},
    {"query": "What about that?", "route": "needs_clarification"},
    {"query": "Give me the last ones", "route": "needs_clarification"},
    {"query": "more", "route": "needs_clarification"},
    {"query": "continue", "route": "needs_clarification"},
]

# System prompt template — reserved for LLM-assisted routing (future task).
ROUTING_SYSTEM_PROMPT = """\
You are a query router for a Customer Service Analytics Agent.
Classify the user query into exactly one of:
  structured          — requires counting, filtering, or aggregating dataset records
  unstructured        — requires summarization or open-ended explanation of dataset content
  out_of_scope        — not related to the Bitext Customer Support dataset
  needs_clarification — ambiguous or requires prior context to interpret

Return ONLY a JSON object with these keys:
  route, confidence, reason_summary, next_action

Do NOT include chain-of-thought or internal reasoning in the response.

Examples:
{examples}
"""


def build_routing_prompt(query: str) -> str:
    """Format a routing prompt with few-shot examples.

    Not used by the current deterministic router — reserved for future LLM routing.
    """
    example_lines = "\n".join(
        f'  Query: "{ex["query"]}" → {ex["route"]}'
        for ex in FEW_SHOT_EXAMPLES[:8]
    )
    return ROUTING_SYSTEM_PROMPT.format(examples=example_lines) + f'\nUser query: "{query}"'
