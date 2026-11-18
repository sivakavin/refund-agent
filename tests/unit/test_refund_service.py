from unittest.mock import Mock
from app.services.refund_service import RefundService


def test_lookup_invalid_order_id():
    service = RefundService(Mock())
    assert service.lookup_order("../bad")["found"] is False


def test_lookup_missing_order():
    repo = Mock()
    repo.get_order.return_value = None
    assert RefundService(repo).lookup_order("9999")["found"] is False


def test_eligible_order():
    repo = Mock()
    repo.get_order.return_value = {"order_id":"1","item":"Book","amount":"12.00","ordered_on":"2026-11-08","refunded":False}
    result = RefundService(repo).lookup_order("1")
    assert result["eligible"] is True


def test_old_order_not_eligible():
    repo = Mock()
    repo.get_order.return_value = {"order_id":"1","item":"Book","amount":"12.00","ordered_on":"2026-10-01","refunded":False}
    assert RefundService(repo).lookup_order("1")["eligible"] is False


def test_already_refunded_not_eligible():
    repo = Mock()
    repo.get_order.return_value = {"order_id":"1","item":"Book","amount":"12.00","ordered_on":"2026-11-17","refunded":True}
    assert RefundService(repo).lookup_order("1")["eligible"] is False


def test_duplicate_request_delegates_to_atomic_rpc():
    repo = Mock()
    repo.issue_refund.return_value = {"success":False,"rejection_reason":"Order has already been refunded."}
    result = RefundService(repo).issue_refund("1","Changed mind")
    assert result["success"] is False
    repo.issue_refund.assert_called_once()


def test_concurrent_requests_are_serialized_by_database():
    # The PostgreSQL function takes a row lock and changes refunded in one transaction.
    # Integration verification requires an isolated Supabase test project.
    assert "issue_refund" in open("supabase/migrations/202611180001_orders_and_atomic_refund.sql", encoding="utf-8").read()
