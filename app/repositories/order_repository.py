from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from supabase import Client


class RepositoryError(RuntimeError):
    """Database operation failed."""


class OrderRepository:
    def __init__(self, client: Client):
        self.client = client

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        try:
            result = self.client.table("orders").select("*").eq("order_id", order_id).maybe_single().execute()
            return result.data
        except Exception as exc:
            raise RepositoryError("Order lookup failed") from exc

    def refund_status(self, order_id: str) -> bool | None:
        order = self.get_order(order_id)
        return None if order is None else bool(order["refunded"])

    def issue_refund(self, order_id: str, reason: str, window_days: int) -> dict[str, Any]:
        try:
            result = self.client.rpc(
                "issue_refund",
                {"p_order_id": order_id, "p_reason": reason, "p_window_days": window_days},
            ).execute()
            data = result.data
            return data[0] if isinstance(data, list) and data else data
        except Exception as exc:
            raise RepositoryError("Refund operation failed") from exc


def order_age_days(order: dict[str, Any], today: date | None = None) -> int:
    ordered_on = order["ordered_on"]
    if isinstance(ordered_on, str):
        ordered_on = date.fromisoformat(ordered_on)
    return ((today or date.today()) - ordered_on).days
