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
from app.services.refund_service import RefundService
from evals.evaluators import (
    deterministic_policy_check,
    execution_success_check,
    response_check,
    tool_selection_check,
)

ROOT = Path(__file__).resolve().parents[1]
ORDER_OWNERS = {"4521": "siva", "7788": "inba", "1002": "soundhu"}


class FixtureRepository:
    """In-memory fixture data. This class never connects to Supabase."""

    def __init__(self, user_name: str):
        self.user_name = user_name
        today = date.today()
        self.orders: dict[str, dict[str, Any]] = {
            "4521": {"order_id":"4521","item":"Bluetooth Speaker","amount":"2499.00","ordered_on":(today-timedelta(days=10)).isoformat(),"refunded":False},
            "7788": {"order_id":"7788","item":"Running Shoes","amount":"3999.00","ordered_on":(today-timedelta(days=45)).isoformat(),"refunded":False},
            "1002": {"order_id":"1002","item":"Phone Cover","amount":"499.00","ordered_on":(today-timedelta(days=3)).isoformat(),"refunded":True},
        }

    def list_orders(self):
        return [
            order for order_id, order in self.orders.items()
            if ORDER_OWNERS[order_id] == self.user_name
        ]

    def get_order(self, order_id: str):
        if ORDER_OWNERS.get(order_id) != self.user_name:
            return None
        return self.orders.get(order_id)

    def issue_refund(self, order_id: str, reason: str, window_days: int):
        order = self.get_order(order_id)
        if order is None:
            return {"success":False,"order_id":order_id,"rejection_reason":"Order not found for this account."}
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


def _tool_result(messages: list[Any]) -> tuple[str | None, dict | None]:
    actual_tool = None
    result = None
    for message in messages:
        for call in getattr(message, "tool_calls", []):
            if actual_tool is None:
                actual_tool = call.get("name")
        if isinstance(message, ToolMessage):
            try:
                value = json.loads(message.content) if isinstance(message.content, str) else message.content
                if isinstance(value, dict):
                    result = value
            except (json.JSONDecodeError, TypeError):
                result = {"tool_error": True}
    return actual_tool, result


async def run_case(case: dict, model_name: str) -> dict:
    user_name = case.get("user_name", "siva")
    repository = FixtureRepository(user_name)
    service = RefundService(repository, refund_window_days=30)
    model = ChatGroq(model=model_name, temperature=0)
    graph = build_graph(model, service, user_name)
    try:
        state = await graph.ainvoke(
            {"messages":[HumanMessage(content=case["input"])]},
            config={"configurable":{"thread_id":f"eval-{user_name}-{case['id']}"}},
        )
        messages = state["messages"]
        answer = str(messages[-1].content)
        actual_tool, tool_result = _tool_result(messages)
        expected_tool = case.get("expected_tool")
        scores = {
            "task_completion": bool(answer.strip()) and (
                actual_tool == expected_tool
                or (case.get("expected_policy") == "ask_order_id" and expected_tool is None)
            ),
            "tool_selection": tool_selection_check(actual_tool, expected_tool),
            "refund_policy_compliance": deterministic_policy_check(
                tool_result, case["expected_policy"], answer
            ),
            "response_correctness": response_check(
                answer, case.get("required_terms"), case.get("required_any")
            ),
            "tool_execution_success": execution_success_check(tool_result, expected_tool),
        }
        return {
            "id":case["id"], "user_name":user_name, "input":case["input"], "answer":answer,
            "selected_tool":actual_tool, "tool_result":tool_result, "scores":scores,
            "score":round(sum(scores.values())/len(scores), 3),
        }
    except Exception as exc:
        return {
            "id":case["id"], "user_name":user_name, "input":case["input"],
            "error":type(exc).__name__,
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
    parser = argparse.ArgumentParser(description="Evaluate the agent with local fixture orders.")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("dataset.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("results.json"))
    args = parser.parse_args()
    if not os.getenv("GROQ_API_KEY"):
        parser.error("Set GROQ_API_KEY in the environment or .env file.")
    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    summary = asyncio.run(run(args.dataset, args.output, model_name))
    print(json.dumps({key:summary[key] for key in ("model","cases","overall_score","metrics")}, indent=2))
    print(f"Per-case results written to {args.output.resolve()}")


if __name__ == "__main__":
    main()
