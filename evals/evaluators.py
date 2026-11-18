from __future__ import annotations


def deterministic_policy_check(tool_result: dict | None, expected_policy: str, answer: str = "") -> bool:
    result = tool_result or {}
    if expected_policy == "eligible":
        return result.get("eligible") is True
    if expected_policy == "allow":
        return result.get("success") is True
    if expected_policy == "deny":
        return bool(result) and result.get("success") is not True and result.get("eligible") is not True
    if expected_policy == "ask_order_id":
        text = answer.casefold()
        return any(term in text for term in ("order id", "order number", "which order", "what order"))
    if expected_policy == "backend_authority":
        return result.get("eligible") is False and result.get("success") is not True
    return False


def tool_selection_check(actual_tool: str | None, expected_tool: str | None) -> bool:
    return actual_tool == expected_tool


def response_check(answer: str, required_terms: list[str] | None = None, required_any: list[str] | None = None) -> bool:
    text = answer.casefold()
    all_match = all(term.casefold() in text for term in (required_terms or []))
    any_terms = required_any or []
    any_match = not any_terms or any(term.casefold() in text for term in any_terms)
    return bool(text.strip()) and all_match and any_match


def execution_success_check(tool_result: dict | None, expected_tool: str | None) -> bool:
    if expected_tool is None:
        return tool_result is None
    return tool_result is not None
