CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address TEXT NOT NULL,
    chain TEXT NOT NULL DEFAULT 'ethereum',
    risk_score INTEGER NOT NULL,
    risk_level TEXT NOT NULL,
    contract_name TEXT,
    symbol TEXT,
    analysis_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address TEXT NOT NULL,
    chain TEXT NOT NULL DEFAULT 'ethereum',
    label TEXT,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(contract_address, chain)
);

CREATE INDEX idx_analyses_address ON analyses(contract_address);
CREATE INDEX idx_analyses_created ON analyses(created_at DESC);
