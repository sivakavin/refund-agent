from typing import Any
from datetime import date
from supabase import Client


class RepositoryError(RuntimeError):
    """Raised when the database cannot complete an operation."""


class OrderRepository:
    """Database access scoped to one demo account."""

    def __init__(self, client: Client, user_name: str):
        self.client = client
        self.user_name = user_name.lower()

    def list_orders(self) -> list[dict[str, Any]]:
        try:
            result = (
                self.client.table("orders")
                .select("*")
                .eq("customer_name", self.user_name)
                .order("ordered_on", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            raise RepositoryError("Order list failed") from exc

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        try:
            result = (
                self.client.table("orders")
                .select("*")
                .eq("customer_name", self.user_name)
                .eq("order_id", order_id)
                .maybe_single()
                .execute()
            )
            return result.data
        except Exception as exc:
            raise RepositoryError("Order lookup failed") from exc

    def issue_refund(self, order_id: str, reason: str, window_days: int) -> dict[str, Any]:
        try:
            result = self.client.rpc(
                "issue_refund",
                {
                    "p_order_id": order_id,
                    "p_reason": reason,
                    "p_window_days": window_days,
                    "p_customer_name": self.user_name,
                },
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
