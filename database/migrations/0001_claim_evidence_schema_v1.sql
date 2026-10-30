-- CIN Step 23 schema v1.0 — SQLite reference migration for local development/tests only.
-- Not wired to application startup. Do not use an ephemeral SQLite file as production storage.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cin_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cin_evidence_records (
    cin_evidence_id TEXT PRIMARY KEY,
    source_namespace TEXT NOT NULL CHECK(length(trim(source_namespace)) BETWEEN 1 AND 128),
    external_evidence_id TEXT,
    evidence_type TEXT NOT NULL CHECK(length(trim(evidence_type)) BETWEEN 1 AND 128),
    created_at TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    CHECK(external_evidence_id IS NULL OR length(trim(external_evidence_id)) BETWEEN 1 AND 256)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cin_evidence_external_identity
ON cin_evidence_records(source_namespace, external_evidence_id)
WHERE external_evidence_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cin_evidence_observations (
    observation_id TEXT PRIMARY KEY,
    cin_evidence_id TEXT NOT NULL REFERENCES cin_evidence_records(cin_evidence_id),
    observed_at TEXT NOT NULL,
    retrieved_at TEXT,
    published_at TEXT,
    checked_at TEXT,
    metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
    metadata_fingerprint_sha256 TEXT NOT NULL CHECK(length(metadata_fingerprint_sha256) = 64),
    content_hash_sha256 TEXT CHECK(content_hash_sha256 IS NULL OR length(content_hash_sha256) = 64),
    source_status TEXT NOT NULL CHECK(source_status IN ('caller_supplied', 'cin_observed', 'cin_retrieved', 'unavailable', 'invalid')),
    schema_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cin_evidence_observations_record_time
ON cin_evidence_observations(cin_evidence_id, observed_at);

CREATE TABLE IF NOT EXISTS cin_claims (
    claim_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL CHECK(length(trim(subject)) BETWEEN 1 AND 512),
    predicate TEXT NOT NULL CHECK(length(trim(predicate)) BETWEEN 1 AND 128),
    statement TEXT NOT NULL CHECK(length(trim(statement)) BETWEEN 1 AND 4000),
    value_json TEXT CHECK(value_json IS NULL OR json_valid(value_json)),
    unit TEXT,
    valid_time_start TEXT,
    valid_time_end TEXT,
    created_at TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    identifier_method TEXT NOT NULL,
    CHECK(valid_time_start IS NULL OR valid_time_end IS NULL OR valid_time_start <= valid_time_end)
);

CREATE TABLE IF NOT EXISTS cin_claim_assessment_events (
    assessment_event_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES cin_claims(claim_id),
    claim_status TEXT NOT NULL CHECK(claim_status IN ('supported', 'contradicted', 'mixed', 'insufficient_evidence', 'not_assessed')),
    assessed_at TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    assessor_type TEXT NOT NULL CHECK(assessor_type IN ('automated_rule', 'human_reviewer')),
    rationale TEXT NOT NULL CHECK(length(trim(rationale)) BETWEEN 1 AND 4000)
);
CREATE INDEX IF NOT EXISTS ix_cin_claim_assessments_claim_time
ON cin_claim_assessment_events(claim_id, assessed_at);

CREATE TABLE IF NOT EXISTS cin_claim_evidence_relationships (
    relationship_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES cin_claims(claim_id),
    cin_evidence_id TEXT NOT NULL REFERENCES cin_evidence_records(cin_evidence_id),
    relationship_type TEXT NOT NULL CHECK(relationship_type IN ('supports', 'contradicts', 'qualifies', 'context_only')),
    review_status TEXT NOT NULL CHECK(review_status IN ('automated_candidate', 'human_reviewed', 'rejected')),
    rationale TEXT NOT NULL CHECK(length(trim(rationale)) BETWEEN 1 AND 2000),
    created_at TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    UNIQUE(claim_id, cin_evidence_id, relationship_type, created_at)
);
CREATE INDEX IF NOT EXISTS ix_cin_relationship_evidence
ON cin_claim_evidence_relationships(cin_evidence_id);

CREATE TABLE IF NOT EXISTS cin_evidence_conflicts (
    conflict_id TEXT PRIMARY KEY,
    subject_key TEXT NOT NULL,
    metric_or_predicate TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    resolution_status TEXT NOT NULL CHECK(resolution_status IN ('open', 'under_review', 'resolved', 'unresolved')),
    rationale TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cin_evidence_conflict_observations (
    conflict_id TEXT NOT NULL REFERENCES cin_evidence_conflicts(conflict_id),
    observation_id TEXT NOT NULL REFERENCES cin_evidence_observations(observation_id),
    PRIMARY KEY(conflict_id, observation_id)
);

-- Enforce immutable history at the database boundary, not only in adapter methods.
CREATE TRIGGER IF NOT EXISTS trg_cin_evidence_observations_no_update
BEFORE UPDATE ON cin_evidence_observations
BEGIN
    SELECT RAISE(ABORT, 'evidence observations are append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_cin_evidence_observations_no_delete
BEFORE DELETE ON cin_evidence_observations
BEGIN
    SELECT RAISE(ABORT, 'evidence observations are append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_cin_claim_assessment_events_no_update
BEFORE UPDATE ON cin_claim_assessment_events
BEGIN
    SELECT RAISE(ABORT, 'claim assessment events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_cin_claim_assessment_events_no_delete
BEFORE DELETE ON cin_claim_assessment_events
BEGIN
    SELECT RAISE(ABORT, 'claim assessment events are append-only');
END;

INSERT OR IGNORE INTO cin_schema_migrations(version, applied_at)
VALUES ('1.0', 'REFERENCE_ONLY_NOT_APPLIED');
