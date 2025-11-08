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
set timezone = 'utc';

-- Main App Role for Managing Application Objects
create role csb_app;
alter role csb_app with login;
grant connect on database csb_app_db to csb_app;
grant create on schema public to csb_app;

-- Main App Schema, tied to App Role
create schema csb_app authorization csb_app;
grant usage, create on schema csb_app to csb_app;

-- API-Service User Role; Password to be set later on by admin user.
create role csb_api_user;
alter role csb_api_user with login;
grant connect on database csb_app_db to csb_api_user;
grant usage on schema public to csb_api_user;
grant usage on schema csb_app to csb_api_user;

-- AWS-Worker User Role; Password to be set later on by admin user.
create role csb_aws_user;
alter role csb_aws_user with login;
grant connect on database csb_app_db to csb_aws_user;
grant usage on schema public to csb_aws_user;
grant usage on schema csb_app to csb_aws_user;

-- Azure Worker User Role; Password to be set later on by admin user.
create role csb_azure_user;
alter role csb_azure_user with login;
grant connect on database csb_app_db to csb_azure_user;
grant usage on schema public to csb_azure_user;
grant usage on schema csb_app to csb_azure_user;

-- Explicitly REVOKE all other permissions to enforce least privilege.
revoke truncate, delete, references, trigger on all tables in schema public from csb_api_user;
revoke truncate, delete, references, trigger on all tables in schema csb_app from csb_api_user;

revoke truncate, delete, references, trigger on all tables in schema public from csb_aws_user;
revoke truncate, delete, references, trigger on all tables in schema csb_app from csb_aws_user;

revoke truncate, delete, references, trigger on all tables in schema public from csb_azure_user;
revoke truncate, delete, references, trigger on all tables in schema csb_app from csb_azure_user;

-- Set search path for the roles to both public and csb_app
alter role csb_app set search_path = csb_app, public;
alter role csb_api_user set search_path = csb_app, public;
alter role csb_aws_user set search_path = csb_app, public;
alter role csb_azure_user set search_path = csb_app, public;

-- Log a message to the console upon successful completion
\echo 'CSecBridge database initialized successfully with roles, tables, and permissions.'