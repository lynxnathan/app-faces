CREATE TABLE submissions (
 id TEXT PRIMARY KEY, receipt_hash TEXT NOT NULL, payload_hash TEXT NOT NULL,
 application_id TEXT NOT NULL, name TEXT NOT NULL, digest TEXT NOT NULL,
 source_url TEXT NOT NULL, license TEXT NOT NULL, variant TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','correction','merged','revoked')),
 reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 version INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX submission_status ON submissions(status,created_at);
CREATE TABLE applications (id TEXT PRIMARY KEY, name TEXT NOT NULL, digest TEXT NOT NULL, source_url TEXT NOT NULL, license TEXT NOT NULL, variant TEXT NOT NULL);
CREATE TABLE revoked_assets (digest TEXT PRIMARY KEY);
CREATE TABLE reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, operation TEXT UNIQUE NOT NULL, submission_id TEXT, reviewer TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL, previous_status TEXT, revision INTEGER, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE revisions (id INTEGER PRIMARY KEY AUTOINCREMENT, manifest TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
INSERT INTO revisions(manifest) VALUES ('[]');
