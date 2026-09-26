CREATE TABLE submissions_next (
 id TEXT PRIMARY KEY, receipt_hash TEXT NOT NULL, payload_hash TEXT NOT NULL,
 application_id TEXT NOT NULL, name TEXT NOT NULL, digest TEXT NOT NULL,
 source_url TEXT NOT NULL, license TEXT NOT NULL, variant TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','correction','merged','revoked','withdrawn')),
 reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 version INTEGER NOT NULL DEFAULT 0
);
INSERT INTO submissions_next SELECT * FROM submissions;
DROP TABLE submissions;
ALTER TABLE submissions_next RENAME TO submissions;
CREATE INDEX submission_status ON submissions(status,created_at);
CREATE INDEX submission_digest ON submissions(digest);
CREATE TABLE receipt_operations (
 operation TEXT PRIMARY KEY,
 submission_id TEXT NOT NULL,
 key_hash TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 response TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(submission_id,key_hash)
);
