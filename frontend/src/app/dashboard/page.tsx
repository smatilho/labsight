"use client";

import { useState, useEffect } from "react";
import MetricCard from "@/components/MetricCard";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";
import type { DashboardOverview } from "@/lib/types";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/dashboard/overview")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-3.5rem)] text-ops-muted">
        Loading dashboard...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-3.5rem)] text-ops-red">
        Failed to load dashboard: {error}
      </div>
    );
  }

  if (!data) return null;

  // Compute summary metrics
  const totalServices = data.service_health.length;
  const servicesUp = data.service_health.filter((s) => s.status === "up").length;
  const avgUptime = data.uptime_summary.length
    ? (data.uptime_summary.reduce((sum, s) => sum + s.uptime_percent, 0) / data.uptime_summary.length).toFixed(1)
    : "—";
  const totalQueries = data.query_activity.reduce((sum, q) => sum + q.total_queries, 0);
  const avgLatency = data.query_activity.length
    ? (data.query_activity.reduce((sum, q) => sum + q.avg_latency_ms, 0) / data.query_activity.length).toFixed(0)
    : "—";

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <h1 className="text-xl font-bold">Dashboard</h1>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Services" value={`${servicesUp}/${totalServices}`} color="green" subtext="currently up" />
        <MetricCard label="Avg Uptime" value={`${avgUptime}%`} color={Number(avgUptime) >= 99 ? "green" : "amber"} subtext="7-day average" />
        <MetricCard label="Queries (7d)" value={totalQueries} color="blue" />
        <MetricCard label="Avg Latency" value={`${avgLatency}ms`} color="default" subtext="7-day average" />
      </div>

      {/* Service health */}
      <section className="bg-ops-surface border border-ops-border rounded-lg p-4">
        <h2 className="text-sm font-medium text-ops-muted mb-3 uppercase tracking-wider">Service Health</h2>
        <DataTable
          columns={["Service", "Status", "Response Time", "Last Check"]}
          rows={data.service_health.map((s) => ({
            Service: s.service_name,
            Status: <StatusBadge status={s.status} />,
            "Response Time": `${s.response_time_ms?.toFixed(1) ?? "—"}ms`,
            "Last Check": s.checked_at ? new Date(s.checked_at).toLocaleString() : "—",
          }))}
        />
      </section>

      {/* Uptime summary */}
      <section className="bg-ops-surface border border-ops-border rounded-lg p-4">
        <h2 className="text-sm font-medium text-ops-muted mb-3 uppercase tracking-wider">Uptime Summary (7d)</h2>
        <DataTable
          columns={["Service", "Uptime", "Total Checks", "Avg Response"]}
          rows={data.uptime_summary.map((s) => ({
            Service: s.service_name,
            Uptime: <span className={s.uptime_percent >= 99 ? "text-ops-green" : "text-ops-amber"}>{s.uptime_percent}%</span>,
            "Total Checks": s.total_checks,
            "Avg Response": `${s.avg_response_ms?.toFixed(1) ?? "—"}ms`,
          }))}
        />
      </section>

      {/* Resource utilization */}
      <section className="bg-ops-surface border border-ops-border rounded-lg p-4">
        <h2 className="text-sm font-medium text-ops-muted mb-3 uppercase tracking-wider">Resource Utilization</h2>
        <DataTable
          columns={["Node", "CPU", "Memory", "Storage"]}
          rows={data.resource_utilization.map((r) => ({
            Node: r.node,
            CPU: <span className={r.cpu_percent > 80 ? "text-ops-red" : ""}>{r.cpu_percent}%</span>,
            Memory: <span className={r.memory_percent > 80 ? "text-ops-red" : ""}>{r.memory_percent}%</span>,
            Storage: <span className={r.storage_percent > 80 ? "text-ops-red" : ""}>{r.storage_percent}%</span>,
          }))}
        />
      </section>

      {/* Query activity */}
      <section className="bg-ops-surface border border-ops-border rounded-lg p-4">
        <h2 className="text-sm font-medium text-ops-muted mb-3 uppercase tracking-wider">Query Activity (7d)</h2>
        <DataTable
          columns={["Date", "Total", "OK", "Failed", "Avg Latency", "RAG", "Metrics", "Hybrid"]}
          rows={data.query_activity.map((q) => ({
            Date: q.query_date,
            Total: q.total_queries,
            OK: <span className="text-ops-green">{q.successful}</span>,
            Failed: q.failed > 0 ? <span className="text-ops-red">{q.failed}</span> : "0",
            "Avg Latency": `${q.avg_latency_ms?.toFixed(0) ?? "—"}ms`,
            RAG: q.rag_queries,
            Metrics: q.metrics_queries,
            Hybrid: q.hybrid_queries,
          }))}
        />
      </section>

      {/* Recent ingestions */}
      <section className="bg-ops-surface border border-ops-border rounded-lg p-4">
        <h2 className="text-sm font-medium text-ops-muted mb-3 uppercase tracking-wider">Recent Ingestions</h2>
        <DataTable
          columns={["File", "Type", "Status", "Chunks", "Time"]}
          rows={data.recent_ingestions.map((ing) => ({
            File: ing.file_name,
            Type: ing.file_type,
            Status: <StatusBadge status={ing.status} />,
            Chunks: ing.chunk_count,
            Time: `${ing.total_time_ms?.toFixed(0) ?? "—"}ms`,
          }))}
        />
      </section>
    </div>
  );
}
