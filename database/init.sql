-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Core event table
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- When
    start_datetime TIMESTAMPTZ NOT NULL,
    end_datetime TIMESTAMPTZ,

    -- Where
    venue_name VARCHAR(255),
    address TEXT,
    location GEOGRAPHY(POINT, 4326),
    district VARCHAR(100),

    -- Categorization
    category VARCHAR(50),
    tags TEXT[],

    -- Source tracking
    source VARCHAR(50),
    source_url TEXT,
    source_id VARCHAR(255),

    -- Media
    image_url TEXT,

    -- Metadata
    price_info VARCHAR(100),
    organizer_name VARCHAR(255),

    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    is_featured BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial index for location queries
CREATE INDEX IF NOT EXISTS idx_events_location ON events USING GIST(location);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_events_search ON events USING GIN(
    to_tsvector('english', title || ' ' || COALESCE(description, ''))
);

-- Index for common filters
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_start_datetime ON events(start_datetime);
CREATE INDEX IF NOT EXISTS idx_events_district ON events(district);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
CREATE INDEX IF NOT EXISTS idx_events_source_id ON events(source, source_id);

-- No seed data - events will be populated by scrapers
-- Run the scraper to populate with real Bangkok events:
-- ENABLE_SCRAPER=true python -c "from app.services.scraper_runner import run_scrapers; run_scrapers()"
