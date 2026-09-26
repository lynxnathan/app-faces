-- PNGs are <=256 KiB, below D1's row limit. No billable object-store binding.
CREATE TABLE artwork (
 digest TEXT PRIMARY KEY,
 png BLOB NOT NULL CHECK(length(png) BETWEEN 57 AND 262144)
);
CREATE INDEX submission_digest ON submissions(digest);
CREATE INDEX application_digest ON applications(digest);
