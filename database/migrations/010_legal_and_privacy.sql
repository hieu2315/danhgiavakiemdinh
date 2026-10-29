ALTER TABLE orders ADD COLUMN accepted_terms_version TEXT;
ALTER TABLE orders ADD COLUMN terms_accepted_at INTEGER;

CREATE TABLE privacy_requests(
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 request_type TEXT NOT NULL CHECK(request_type IN ('access','correction','deletion','objection','other')),
 details TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','completed','rejected')),
 resolution_note TEXT NOT NULL DEFAULT '',
 created_at INTEGER NOT NULL,
 updated_at INTEGER NOT NULL
);
CREATE INDEX idx_privacy_requests_user ON privacy_requests(user_id,created_at DESC);
CREATE INDEX idx_privacy_requests_status ON privacy_requests(status,created_at DESC);
