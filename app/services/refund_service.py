import re
from datetime import date
from typing import Any
from app.repositories.order_repository import OrderRepository


ORDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class RefundService:
    """Refund rules and order formatting. Database work stays in OrderRepository."""

    def __init__(self, repository: OrderRepository, refund_window_days: int = 30):
        self.repository = repository
        self.refund_window_days = refund_window_days

    def list_orders(self) -> list[dict[str, Any]]:
        return [self._order_summary(order) for order in self.repository.list_orders()]

    def lookup_order(self, order_id: str) -> dict[str, Any]:
        if not ORDER_ID_RE.fullmatch(order_id):
            return {"found": False, "order_id": order_id, "reason": "Invalid order ID format."}

        order = self.repository.get_order(order_id)
        if not order:
            return {"found": False, "order_id": order_id, "reason": "Order not found for this account."}
        return {"found": True, **self._order_summary(order)}

    def issue_refund(self, order_id: str, reason: str) -> dict[str, Any]:
        if not ORDER_ID_RE.fullmatch(order_id):
            return {"success": False, "order_id": order_id, "reason": "Invalid order ID format."}
        if not reason.strip():
            return {"success": False, "order_id": order_id, "reason": "A refund reason is required."}
        return self.repository.issue_refund(
            order_id,
            reason.strip()[:500],
            self.refund_window_days,
        )

    def _order_summary(self, order: dict[str, Any]) -> dict[str, Any]:
        age = self._order_age_days(order)
        refunded = bool(order.get("refunded", False))
        eligible = not refunded and 0 <= age <= self.refund_window_days
        reason = None
        if refunded:
            reason = "This order has already been refunded."
        elif age < 0 or age > self.refund_window_days:
            reason = f"Orders must be within {self.refund_window_days} days; this order is {age} days old."

        return {
            "order_id": order["order_id"],
            "item": order["item"],
            "amount": str(order["amount"]),
            "ordered_on": str(order["ordered_on"]),
            "order_age_days": age,
            "refunded": refunded,
            "eligible": eligible,
            "eligibility_reason": reason,
        }

    @staticmethod
    def _order_age_days(order: dict[str, Any]) -> int:
        ordered_on = order["ordered_on"]
        if isinstance(ordered_on, str):
            ordered_on = date.fromisoformat(ordered_on)
        return (date.today() - ordered_on).days
