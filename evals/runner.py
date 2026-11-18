from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_groq import ChatGroq

from app.agents.graph import build_graph
from app.repositories.order_repository import OrderRepository
from app.services.refund_service import RefundService
from evals.evaluators import (
    deterministic_policy_check,
    execution_success_check,
    response_check,
    tool_selection_check,
)

ROOT = Path(__file__).resolve().parents[1]


class FixtureRepository:
    """In-memory order store for evaluations. It has no Supabase client or network access."""

    def __init__(self):
        today = date.today()
        self.orders: dict[str, dict[str, Any]] = {
            "4521": {"order_id":"4521","item":"Bluetooth Speaker","amount":"2499.00","ordered_on":(today-timedelta(days=10)).isoformat(),"refunded":False},
            "7788": {"order_id":"7788","item":"Running Shoes","amount":"3999.00","ordered_on":(today-timedelta(days=45)).isoformat(),"refunded":False},
            "1002": {"order_id":"1002","item":"Phone Cover","amount":"499.00","ordered_on":(today-timedelta(days=3)).isoformat(),"refunded":True},
        }

    def get_order(self, order_id: str):
        return self.orders.get(order_id)

    def issue_refund(self, order_id: str, reason: str, window_days: int):
        order = self.orders.get(order_id)
        if order is None:
            return {"success":False,"order_id":order_id,"rejection_reason":"Order not found."}
        if order["refunded"]:
            return {"success":False,"order_id":order_id,"rejection_reason":"Order has already been refunded."}
        age = (date.today() - date.fromisoformat(order["ordered_on"])).days
        if age < 0 or age > window_days:
            return {"success":False,"order_id":order_id,"rejection_reason":"Order is outside the refund window."}
        if not reason.strip():
            return {"success":False,"order_id":order_id,"rejection_reason":"A refund reason is required."}
        order["refunded"] = True
        order["refund_reason"] = reason
        return {"success":True,"order_id":order_id,"refund_amount":order["amount"]}


def _tool_result(messages: list[Any], expected_tool: str | None) -> tuple[str | None, dict | None]:
    actual_tool = None
    result = None
    for message in messages:
        if getattr(message, "tool_calls", None):
            for call in message.tool_calls:
                name = call.get("name")
                if actual_tool is None:
                    actual_tool = name
        if isinstance(message, ToolMessage):
            try:
                value = json.loads(message.content) if isinstance(message.content, str) else message.content
                if isinstance(value, dict):
                    result = value
            except (json.JSONDecodeError, TypeError):
                result = {"tool_error": True}
    return actual_tool, result


async def run_case(case: dict, model_name: str) -> dict:
    repository = FixtureRepository()
    service = RefundService(OrderRepository(repository), refund_window_days=30)
    model = ChatGroq(model=model_name, temperature=0)
    graph = build_graph(model, service)
    try:
        state = await graph.ainvoke(
            {"messages":[HumanMessage(content=case["input"])]},
            config={"configurable":{"thread_id":f"eval-{case['id']}"}},
        )
        messages = state["messages"]
        answer = str(messages[-1].content)
        actual_tool, tool_result = _tool_result(messages, case.get("expected_tool"))
        scores = {
            "task_completion": bool(answer.strip()) and (
                actual_tool == case.get("expected_tool")
                or (case.get("expected_policy") == "ask_order_id" and case.get("expected_tool") is None)
            ),
            "tool_selection": tool_selection_check(actual_tool, case.get("expected_tool")),
            "refund_policy_compliance": deterministic_policy_check(
                tool_result, case["expected_policy"], answer
            ),
            "response_correctness": response_check(
                answer, case.get("required_terms"), case.get("required_any")
            ),
            "tool_execution_success": execution_success_check(tool_result, case.get("expected_tool")),
        }
        return {
            "id":case["id"], "input":case["input"], "answer":answer,
            "selected_tool":actual_tool, "tool_result":tool_result, "scores":scores,
            "score":round(sum(scores.values())/len(scores), 3),
        }
    except Exception as exc:
        return {
            "id":case["id"], "input":case["input"], "error":type(exc).__name__,
            "scores":{"task_completion":False,"tool_selection":False,
                      "refund_policy_compliance":False,"response_correctness":False,
                      "tool_execution_success":False},
            "score":0.0,
        }


async def run(dataset_path: Path, output_path: Path, model_name: str) -> dict:
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    results = [await run_case(case, model_name) for case in cases]
    metric_names = list(results[0]["scores"]) if results else []
    summary = {
        "model":model_name,
        "cases":len(results),
        "overall_score":round(
            sum(sum(result["scores"].values()) for result in results)
            / (len(results)*len(metric_names)), 3
        ) if results and metric_names else 0.0,
        "metrics":{
            name:round(sum(result["scores"][name] for result in results)/len(results), 3)
            if results else 0.0
            for name in metric_names
        },
        "results":results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Run refund agent evaluations against in-memory fixtures.")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("dataset.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("results.json"))
    args = parser.parse_args()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        parser.error("Set GROQ_API_KEY in the environment or .env file.")
    os.environ.setdefault("LANGSMITH_PROJECT", os.getenv("LANGSMITH_PROJECT", "refund-agent-evals"))
    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    summary = asyncio.run(run(args.dataset, args.output, model_name))
    print(json.dumps({key:summary[key] for key in ("model","cases","overall_score","metrics")}, indent=2))
    print(f"Per-case results written to {args.output.resolve()}")


if __name__ == "__main__":
    main()
