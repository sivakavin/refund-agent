-- Assign the three sample orders to demo accounts. Other existing orders remain unassigned.
ALTER TABLE public.orders
ADD COLUMN IF NOT EXISTS customer_name TEXT;

UPDATE public.orders SET customer_name = 'siva' WHERE order_id = '4521';
UPDATE public.orders SET customer_name = 'inba' WHERE order_id = '7788';
UPDATE public.orders SET customer_name = 'soundhu' WHERE order_id = '1002';

CREATE INDEX IF NOT EXISTS orders_customer_name_ordered_on_idx
ON public.orders(customer_name, ordered_on DESC);

-- Replace the unscoped function with an account-scoped atomic refund operation.
DROP FUNCTION IF EXISTS public.issue_refund(TEXT, TEXT, INTEGER);

CREATE FUNCTION public.issue_refund(
    p_order_id TEXT,
    p_reason TEXT,
    p_window_days INTEGER,
    p_customer_name TEXT
)
RETURNS TABLE(success BOOLEAN, order_id TEXT, refund_amount NUMERIC, rejection_reason TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_order public.orders%ROWTYPE;
BEGIN
    SELECT * INTO v_order
    FROM public.orders
    WHERE orders.order_id = p_order_id
      AND orders.customer_name = lower(p_customer_name)
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, p_order_id, NULL::NUMERIC, 'Order not found for this account.';
        RETURN;
    END IF;
    IF v_order.refunded THEN
        RETURN QUERY SELECT FALSE, p_order_id, NULL::NUMERIC, 'Order has already been refunded.';
        RETURN;
    END IF;
    IF v_order.ordered_on > CURRENT_DATE OR v_order.ordered_on < CURRENT_DATE - p_window_days THEN
        RETURN QUERY SELECT FALSE, p_order_id, NULL::NUMERIC, 'Order is outside the refund window.';
        RETURN;
    END IF;
    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RETURN QUERY SELECT FALSE, p_order_id, NULL::NUMERIC, 'A refund reason is required.';
        RETURN;
    END IF;

    UPDATE public.orders
    SET refunded = TRUE, refund_reason = left(btrim(p_reason), 500), refunded_at = NOW()
    WHERE orders.order_id = p_order_id
      AND orders.customer_name = lower(p_customer_name)
      AND refunded = FALSE;

    RETURN QUERY SELECT TRUE, p_order_id, v_order.amount, NULL::TEXT;
END;
$$;

REVOKE ALL ON FUNCTION public.issue_refund(TEXT, TEXT, INTEGER, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.issue_refund(TEXT, TEXT, INTEGER, TEXT) TO service_role;
