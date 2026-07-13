CREATE OR REPLACE FUNCTION notify_ai_sql_copilot_change()
RETURNS TRIGGER AS $$
DECLARE
    payload JSONB;
BEGIN
    payload = jsonb_build_object(
        'table', TG_TABLE_NAME,
        'operation', TG_OP,
        'record', to_jsonb(COALESCE(NEW, OLD)),
        'changed_at', NOW()
    );

    PERFORM pg_notify('ai_sql_copilot_changes', payload::TEXT);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS notify_workspaces_change ON workspaces;
CREATE TRIGGER notify_workspaces_change
AFTER INSERT OR UPDATE OR DELETE ON workspaces
FOR EACH ROW EXECUTE FUNCTION notify_ai_sql_copilot_change();

DROP TRIGGER IF EXISTS notify_database_connections_change ON database_connections;
CREATE TRIGGER notify_database_connections_change
AFTER INSERT OR UPDATE OR DELETE ON database_connections
FOR EACH ROW EXECUTE FUNCTION notify_ai_sql_copilot_change();

DROP TRIGGER IF EXISTS notify_schema_snapshots_change ON schema_snapshots;
CREATE TRIGGER notify_schema_snapshots_change
AFTER INSERT OR UPDATE OR DELETE ON schema_snapshots
FOR EACH ROW EXECUTE FUNCTION notify_ai_sql_copilot_change();

DROP TRIGGER IF EXISTS notify_query_history_change ON query_history;
CREATE TRIGGER notify_query_history_change
AFTER INSERT OR UPDATE OR DELETE ON query_history
FOR EACH ROW EXECUTE FUNCTION notify_ai_sql_copilot_change();

DROP TRIGGER IF EXISTS notify_user_preferences_change ON user_preferences;
CREATE TRIGGER notify_user_preferences_change
AFTER INSERT OR UPDATE OR DELETE ON user_preferences
FOR EACH ROW EXECUTE FUNCTION notify_ai_sql_copilot_change();

DROP TRIGGER IF EXISTS notify_saved_queries_change ON saved_queries;
CREATE TRIGGER notify_saved_queries_change
AFTER INSERT OR UPDATE OR DELETE ON saved_queries
FOR EACH ROW EXECUTE FUNCTION notify_ai_sql_copilot_change();

DROP TRIGGER IF EXISTS notify_audit_events_change ON audit_events;
CREATE TRIGGER notify_audit_events_change
AFTER INSERT OR UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION notify_ai_sql_copilot_change();
