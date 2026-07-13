"use client";

import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ExecuteQueryResponse } from "../lib/types";

export function VisualizationPanel({ result }: { result: ExecuteQueryResponse | null }) {
  const chart = buildChart(result);

  return (
    <section className="panel">
      <h2 className="section-title">Visualization</h2>
      <p>{result?.visualization_suggestion ?? "Run a query to get a chart suggestion."}</p>
      {result ? <p className="muted">{result.summary}</p> : null}
      {chart ? (
        <div style={{ width: "100%", height: 220 }}>
          <ResponsiveContainer>
            {chart.kind === "line" ? (
              <LineChart data={chart.data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={chart.xKey} />
                <YAxis />
                <Tooltip />
                <Line dataKey={chart.yKey} stroke="#0f766e" dot={false} />
              </LineChart>
            ) : (
              <BarChart data={chart.data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={chart.xKey} />
                <YAxis />
                <Tooltip />
                <Bar dataKey={chart.yKey} fill="#0f766e" />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      ) : null}
    </section>
  );
}

function buildChart(result: ExecuteQueryResponse | null) {
  if (!result || result.rows.length === 0) return null;
  const numericColumn = result.columns.find((column) => result.rows.some((row) => isNumericValue(row[column])));
  if (!numericColumn) return null;
  const dateColumn = result.columns.find(
    (column) => /date|time|month|year|day/i.test(column) || result.rows.some((row) => isDateValue(row[column]))
  );
  const categoryColumn = result.columns.find((column) => column !== numericColumn);
  const xKey = dateColumn ?? categoryColumn;
  if (!xKey) return null;
  return {
    kind: dateColumn ? "line" : "bar",
    xKey,
    yKey: numericColumn,
    data: result.rows.slice(0, 50).map((row) => ({
      ...row,
      [numericColumn]: Number(row[numericColumn])
    }))
  };
}

function isNumericValue(value: unknown) {
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value !== "string" || value.trim() === "") return false;
  return Number.isFinite(Number(value));
}

function isDateValue(value: unknown) {
  if (typeof value !== "string" || value.trim() === "") return false;
  return !Number.isNaN(Date.parse(value));
}
