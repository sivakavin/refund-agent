from langchain_core.tools import tool
from app.services.refund_service import RefundService


def build_refund_tools(service: RefundService):
    @tool
    def lookup_order(order_id: str) -> dict:
        """Look up an order's details, recorded refund status, age, and backend-calculated eligibility."""
        return service.lookup_order(order_id)

    @tool
    def issue_refund(order_id: str, reason: str) -> dict:
        """Record a simulated refund approval when the backend refund policy permits it."""
        return service.issue_refund(order_id, reason)

    return [lookup_order, issue_refund]
