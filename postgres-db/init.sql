/* ----------------------------------------------------------------------------
 * CSecBridge Database Initialization Script
 *
 * PURPOSE:
 * This script is responsible for bootstrapping the PostgreSQL database schema
 * for the CSecBridge application. It creates all necessary roles, tables,
 * indexes, and permissions required for the services to function.
 *
 * EXECUTION LIFECYCLE:
 * This script is designed to be executed ONLY ONCE, during the very first
 * startup of the PostgreSQL container against an empty data volume. The
 * official PostgreSQL Docker image's entrypoint handles this automatically.
 *
 * STATE MANAGEMENT AND PERSISTENCE:
 * In a Kubernetes environment, this container is deployed as a StatefulSet
 * with a PersistentVolumeClaim. This ensures that the database's data
 * directory (/var/lib/postgresql/data) is stored on a durable, persistent
 * volume outside the container's lifecycle.
 *
 * On subsequent restarts or redeployments, the new container will attach to
 * the existing persistent volume. Since the data directory is not empty, the
 * entrypoint script will SKIP the execution of this init.sql file, thereby
 * preserving the database's state.
 * 
 * NAMING CONVENTIONS:
 * All custom database objects created for this application - users, tables, 
 * indexes etc. should be prefixed with 'csb_' to avoid conflicts and 
 * improve clarity. Columns are excluded from this convention for readability.
 * 
 */ ---------------------------------------------------------------------------

-- Set timezone to UTC for consistency across the application
SET TIMEZONE = 'UTC';

-- Main App Role for Managing Application Objects
CREATE ROLE CSB_APP;
ALTER ROLE CSB_APP WITH LOGIN;
GRANT CONNECT ON DATABASE CSB_APP_DB TO CSB_APP;
GRANT CREATE ON SCHEMA PUBLIC TO CSB_APP;

-- Main App Schema, tied to App Role
CREATE SCHEMA CSB_APP AUTHORIZATION CSB_APP;
GRANT USAGE, CREATE ON SCHEMA CSB_APP TO CSB_APP;

-- API-Service User Role; Password to be set later on by admin user.
CREATE ROLE CSB_API_USER;
ALTER ROLE CSB_API_USER WITH LOGIN;
GRANT CONNECT ON DATABASE CSB_APP_DB TO CSB_API_USER;
GRANT USAGE ON SCHEMA PUBLIC TO CSB_API_USER;
GRANT USAGE ON SCHEMA CSB_APP TO CSB_API_USER;

-- AWS-Worker User Role; Password to be set later on by admin user.
CREATE ROLE CSB_AWS_USER;
ALTER ROLE CSB_AWS_USER WITH LOGIN;
GRANT CONNECT ON DATABASE CSB_APP_DB TO CSB_AWS_USER;
GRANT USAGE ON SCHEMA PUBLIC TO CSB_AWS_USER;
GRANT USAGE ON SCHEMA CSB_APP TO CSB_AWS_USER;

-- Azure Worker User Role; Password to be set later on by admin user.
CREATE ROLE CSB_AZURE_USER;
ALTER ROLE CSB_AZURE_USER WITH LOGIN;
GRANT CONNECT ON DATABASE CSB_APP_DB TO CSB_AZURE_USER;
GRANT USAGE ON SCHEMA PUBLIC TO CSB_AZURE_USER;
GRANT USAGE ON SCHEMA CSB_APP TO CSB_AZURE_USER;


-- Explicitly REVOKE all other permissions to enforce least privilege.
REVOKE TRUNCATE, DELETE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA PUBLIC FROM CSB_API_USER;
REVOKE TRUNCATE, DELETE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA CSB_APP FROM CSB_API_USER;

-- Set search path for the roles to both public and csb_app
ALTER ROLE CSB_APP SET SEARCH_PATH = CSB_APP, PUBLIC;
ALTER ROLE CSB_API_USER SET SEARCH_PATH = CSB_APP, PUBLIC;

-- Log a message to the console upon successful completion
\echo 'CSecBridge database initialized successfully with roles, tables, and permissions.'