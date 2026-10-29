-- Financial and fulfillment records are corrected by status/history entries, not hard-deleted.
CREATE TRIGGER IF NOT EXISTS trg_orders_no_hard_delete
BEFORE DELETE ON orders BEGIN
 SELECT RAISE(ABORT,'Orders are retained; cancel or archive with status instead of deleting');
END;
CREATE TRIGGER IF NOT EXISTS trg_order_items_no_hard_delete
BEFORE DELETE ON order_items BEGIN
 SELECT RAISE(ABORT,'Order items are retained with their transaction');
END;
CREATE TRIGGER IF NOT EXISTS trg_payment_transactions_no_hard_delete
BEFORE DELETE ON payment_transactions BEGIN
 SELECT RAISE(ABORT,'Payment transactions are retained for reconciliation');
END;
CREATE TRIGGER IF NOT EXISTS trg_order_status_history_no_hard_delete
BEFORE DELETE ON order_status_history BEGIN
 SELECT RAISE(ABORT,'Order status history is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_payment_status_history_no_hard_delete
BEFORE DELETE ON payment_status_history BEGIN
 SELECT RAISE(ABORT,'Payment status history is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_points_ledger_no_hard_delete
BEFORE DELETE ON points_ledger BEGIN
 SELECT RAISE(ABORT,'Points ledger is append-only; record a reversal instead');
END;
CREATE TRIGGER IF NOT EXISTS trg_voucher_redemptions_no_hard_delete
BEFORE DELETE ON voucher_redemptions BEGIN
 SELECT RAISE(ABORT,'Voucher redemption history is retained');
END;
CREATE TRIGGER IF NOT EXISTS trg_impact_snapshots_no_hard_delete
BEFORE DELETE ON impact_snapshots BEGIN
 SELECT RAISE(ABORT,'Completed transaction impact snapshots are retained');
END;

CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_payment_expiry ON orders(payment_status,payment_expires_at);
CREATE INDEX IF NOT EXISTS idx_order_items_product_order ON order_items(product_id,order_id);
CREATE INDEX IF NOT EXISTS idx_payment_history_source_created ON payment_status_history(source,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity_created ON audit_log(entity_type,entity_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbox_user_created ON notification_outbox(user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rentals_user_status ON rental_reservations(user_id,status,start_date);
