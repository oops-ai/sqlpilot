"use client";

import { useEffect, useState } from "react";
import { databaseEventsUrl } from "../lib/api";
import { DatabaseEvent } from "../lib/types";

export function LiveActivityPanel({ connectionId }: { connectionId: string }) {
  const [status, setStatus] = useState("Disconnected");
  const [events, setEvents] = useState<DatabaseEvent[]>([]);

  useEffect(() => {
    if (!connectionId) {
      setStatus("No connection");
      setEvents([]);
      return;
    }

    const source = new EventSource(databaseEventsUrl(connectionId));
    setStatus("Connecting");

    source.addEventListener("connected", (event) => {
      const payload = parseEvent(event, "connected");
      setStatus("Live");
      setEvents((current) => [payload, ...current].slice(0, 12));
    });

    source.addEventListener("database_change", (event) => {
      const payload = parseEvent(event, "database_change");
      setStatus("Live");
      setEvents((current) => [payload, ...current].slice(0, 12));
    });

    source.addEventListener("heartbeat", () => {
      setStatus("Live");
    });

    source.onerror = () => {
      setStatus("Reconnecting");
    };

    return () => {
      source.close();
    };
  }, [connectionId]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2 className="section-title">Live Activity</h2>
          <p className="muted">PostgreSQL LISTEN/NOTIFY stream</p>
        </div>
        <span className={status === "Live" ? "pill good" : "pill"}>{status}</span>
      </div>
      {events.length === 0 ? (
        <p className="muted">No database events yet.</p>
      ) : (
        <div className="activity-list">
          {events.map((event, index) => (
            <div className="activity-item" key={`${event.eventType}-${event.table ?? event.message ?? index}-${index}`}>
              <strong>{labelFor(event)}</strong>
              <span className="muted">{timeFor(event)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function parseEvent(event: Event, eventType: string): DatabaseEvent {
  const message = event as MessageEvent<string>;
  try {
    return { ...JSON.parse(message.data), eventType };
  } catch {
    return { message: message.data, eventType };
  }
}

function labelFor(event: DatabaseEvent) {
  if (event.eventType === "connected") return "Stream connected";
  if (event.table && event.operation) return `${event.operation} on ${event.table}`;
  return event.message ?? event.eventType;
}

function timeFor(event: DatabaseEvent) {
  if (!event.changed_at) return "now";
  const date = new Date(event.changed_at);
  if (Number.isNaN(date.getTime())) return event.changed_at;
  return date.toLocaleTimeString();
}
