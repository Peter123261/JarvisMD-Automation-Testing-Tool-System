-- MedBench Automation Testing Tool - Database Initialization Script
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Create database if it doesn't exist (usually handled by POSTGRES_DB env var)
-- CREATE DATABASE IF NOT EXISTS medbench_automation;

-- Connect to the database
\c medbench_automation;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE medbench_automation TO medbench;

-- Create schema if needed
-- CREATE SCHEMA IF NOT EXISTS medbench;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully';
END $$;









