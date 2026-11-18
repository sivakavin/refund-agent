def deterministic_policy_check(tool_result: dict, expected_policy: str) -> bool:
    if expected_policy in {"allow", "eligible"}:
        return bool(tool_result.get("eligible", tool_result.get("success", False)))
    if expected_policy == "deny":
        return not bool(tool_result.get("eligible", tool_result.get("success", False)))
    if expected_policy in {"ask_order_id", "backend_authority"}:
        return True
    return False


def tool_selection_check(actual_tool: str | None, expected_tool: str | None) -> bool:
    return actual_tool == expected_tool


def response_check(answer: str, required_terms: list[str]) -> bool:
    text = answer.casefold()
    return all(term.casefold() in text for term in required_terms)


def execution_success_check(tool_result: dict) -> bool:
    return tool_result.get("success") is True or tool_result.get("found") is True
