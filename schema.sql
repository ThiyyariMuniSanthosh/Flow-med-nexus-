-- FlowMed Nexus 2.0 — PostgreSQL / Supabase Schema
-- All records are synthetic demonstration data. No real patient PHI is stored.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE hospitals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    total_beds INTEGER NOT NULL,
    available_beds INTEGER NOT NULL,
    icu_available INTEGER NOT NULL,
    ventilators_available INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Normal',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE beds (
    id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department TEXT NOT NULL,
    ward TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Available', 'Occupied', 'Maintenance')),
    turnaround_est_mins INTEGER DEFAULT 0,
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE patient_flow_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id TEXT NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    hour_slot TEXT NOT NULL,
    department TEXT NOT NULL,
    actual_arrivals INTEGER NOT NULL,
    predicted_arrivals INTEGER NOT NULL,
    avg_wait_mins INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE lab_tests (
    id TEXT PRIMARY KEY,
    patient_alias TEXT NOT NULL, -- Anonymized synthetic alias, never real PHI
    department TEXT NOT NULL,
    test_name TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('Routine', 'Urgent', 'STAT')),
    stage TEXT NOT NULL CHECK (stage IN ('Registered', 'Collected', 'Processing', 'Ready', 'Notified')),
    est_completion_mins INTEGER NOT NULL,
    notification_sent BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE resource_requests (
    id TEXT PRIMARY KEY,
    source_hospital_id TEXT NOT NULL REFERENCES hospitals(id),
    target_hospital_id TEXT NOT NULL REFERENCES hospitals(id),
    resource_type TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    urgency TEXT NOT NULL CHECK (urgency IN ('Standard', 'High', 'Critical')),
    status TEXT NOT NULL CHECK (status IN ('Pending Approval', 'Approved', 'In Transit', 'Fulfilled', 'Declined')),
    notes TEXT,
    approved_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sop_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding_json JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_role TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    details TEXT NOT NULL,
    human_approved BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
