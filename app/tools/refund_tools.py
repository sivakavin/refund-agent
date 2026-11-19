from langchain_core.tools import tool
from app.services.refund_service import RefundService
from app.services.policy_rag_service import PolicyRagService


def build_refund_tools(service: RefundService, policy_service: PolicyRagService | None = None):
    """Create tools already scoped to the account selected by the API."""

    @tool
    def list_orders() -> list[dict]:
        """List all orders belonging to the current demo account."""
        return service.list_orders()

    @tool
    def lookup_order(order_id: str) -> dict:
        """Look up one order belonging to the current demo account."""
        return service.lookup_order(order_id)

    @tool
    def issue_refund(order_id: str, reason: str) -> dict:
        """Record a simulated refund approval if backend policy allows it."""
        return service.issue_refund(order_id, reason)

    tools = [list_orders, lookup_order, issue_refund]

    if policy_service is not None:
        @tool
        def search_refund_policy(question: str) -> dict:
            """Search uploaded refund and return policy documents for relevant written terms."""
            return policy_service.search(question)

        tools.append(search_refund_policy)

    return tools
