CREATE TABLE IF NOT EXISTS public.orders (
    order_id TEXT PRIMARY KEY,
    item TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    ordered_on DATE NOT NULL,
    refunded BOOLEAN NOT NULL DEFAULT FALSE,
    refund_reason TEXT,
    refunded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;

-- No anon/authenticated policies are defined. The backend uses the secret key.
CREATE OR REPLACE FUNCTION public.issue_refund(
    p_order_id TEXT,
    p_reason TEXT,
    p_window_days INTEGER DEFAULT 30
)
RETURNS TABLE(success BOOLEAN, order_id TEXT, refund_amount NUMERIC, rejection_reason TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_order public.orders%ROWTYPE;
BEGIN
    SELECT * INTO v_order FROM public.orders WHERE orders.order_id = p_order_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, p_order_id, NULL::NUMERIC, 'Order not found.';
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
    WHERE orders.order_id = p_order_id AND refunded = FALSE;

    RETURN QUERY SELECT TRUE, p_order_id, v_order.amount, NULL::TEXT;
END;
$$;

REVOKE ALL ON FUNCTION public.issue_refund(TEXT, TEXT, INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.issue_refund(TEXT, TEXT, INTEGER) TO service_role;

-- Seed only absent development examples. Review/remove these before applying outside development.
INSERT INTO public.orders(order_id, item, amount, ordered_on, refunded, refund_reason, refunded_at)
VALUES
 ('4521', 'Bluetooth Speaker', 2499, CURRENT_DATE - 10, FALSE, NULL, NULL),
 ('7788', 'Running Shoes', 3999, CURRENT_DATE - 45, FALSE, NULL, NULL),
 ('1002', 'Phone Cover', 499, CURRENT_DATE - 3, TRUE, 'Development seed', NOW())
ON CONFLICT (order_id) DO NOTHING;
