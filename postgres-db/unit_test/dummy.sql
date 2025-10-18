-- Set timezone to UTC for consistency across the application
SET TIMEZONE = 'UTC';

-- Main App Role for Managing Application Objects
CREATE ROLE CSB_APP;

-- API-Service User Role; Password to be set later on by admin user.
CREATE ROLE CSB_API_USER;
GRANT CONNECT ON DATABASE CSECBRIDGE_DB TO CSB_API_USER;
GRANT USAGE ON SCHEMA PUBLIC TO CSB_API_USER;

-- Explicitly REVOKE all other permissions to enforce least privilege.
REVOKE TRUNCATE, DELETE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA PUBLIC FROM CSB_API_USER;