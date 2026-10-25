import pytest

from src.agent.router import route_query
from src.agent.nodes import _detect_unstructured_action


@pytest.mark.parametrize(
    "query, expected_tool, expected_params",
    [
        (
            "Show examples of customers asking for refunds.",
            "get_filtered_examples",
            {"category": "REFUND", "limit": 5},
        ),
        (
            "Summarize common order cancellation issues.",
            "get_filtered_examples",
            {"intent": "cancel_order", "limit": 5},
        ),
    ],
)
def test_unstructured_tool_selection(
    query, expected_tool, expected_params
):
    result = route_query(query)

    assert result.route == "unstructured"

    tool, params = _detect_unstructured_action(query)

    assert tool == expected_tool
    assert params == expected_params


def test_ambiguous_reference_requires_clarification():
    result = route_query("Tell me about it.")

    assert result.route == "needs_clarification"


def test_population_question_out_of_scope():
    result = route_query(
        "What is the population of London?"
    )

    assert result.route == "out_of_scope"

def test_cancel_order_tool_selection():
    tool, params = _detect_unstructured_action(
        "Summarize common order cancellation issues."
    )

    assert tool == "get_filtered_examples"
    assert params == {
        "intent": "cancel_order",
        "limit": 5,
    }

from unittest.mock import patch

from src.agent.nodes import node_unstructured_retrieval


def test_refund_retrieval_executes_filtered_tool():
    fake_rows = [
        {
            "category": "REFUND",
            "intent": "request_refund",
            "instruction": "I would like a refund.",
        }
    ]

    with patch(
        "src.agent.nodes.get_filtered_examples",
        return_value=fake_rows,
    ) as filtered_mock:
        result = node_unstructured_retrieval({
            "query": "Show refund requests",
            "trace": [],
        })

    assert result["selected_tool"] == "get_filtered_examples"
    assert result["tool_input"]["category"] == "REFUND"

    filtered_mock.assert_called_once()

    assert result["observation"] == fake_rows
    assert "I would like a refund." in result["final_answer"]
    assert result["response"] == result["final_answer"]