import re
from datetime import date
from typing import Any
from app.repositories.order_repository import OrderRepository, RepositoryError, order_age_days


ORDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class RefundService:
    def __init__(self, repository: OrderRepository, refund_window_days: int = 30):
        self.repository = repository
        self.refund_window_days = refund_window_days

    def lookup_order(self, order_id: str) -> dict[str, Any]:
        if not ORDER_ID_RE.fullmatch(order_id):
            return {"found": False, "order_id": order_id, "reason": "Invalid order ID format."}
        try:
            order = self.repository.get_order(order_id)
        except RepositoryError:
            raise
        if not order:
            return {"found": False, "order_id": order_id, "reason": "Order not found."}
        age = order_age_days(order)
        refunded = bool(order.get("refunded", False))
        eligible = not refunded and 0 <= age <= self.refund_window_days
        reason = None if eligible else (
            "This order has already been refunded." if refunded
            else f"Orders must be within {self.refund_window_days} days; this order is {age} days old."
        )
        return {
            "found": True, "order_id": order["order_id"], "item": order["item"],
            "amount": str(order["amount"]), "order_age_days": age, "refunded": refunded,
            "eligible": eligible, "eligibility_reason": reason,
        }

    def issue_refund(self, order_id: str, reason: str) -> dict[str, Any]:
        if not ORDER_ID_RE.fullmatch(order_id):
            return {"success": False, "order_id": order_id, "reason": "Invalid order ID format."}
        if not reason.strip():
            return {"success": False, "order_id": order_id, "reason": "A refund reason is required."}
        return self.repository.issue_refund(order_id, reason.strip()[:500], self.refund_window_days)
