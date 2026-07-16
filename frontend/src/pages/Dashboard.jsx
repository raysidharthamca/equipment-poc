import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { usePolling } from "../hooks";
import { Card, StateBadge, StatusDot, statusMeta } from "../components/ui";

function SummaryBar({ summary }) {
  const items = [
    { key: "green", label: "Healthy" },
    { key: "orange", label: "Due Soon" },
    { key: "red", label: "Overdue / Attention" },
  ];
  return (
    <div className="grid grid-cols-3 gap-4">
      {items.map((it) => {
        const meta = statusMeta(it.key);
        return (
          <Card key={it.key} className={`border-l-8 ${meta.border}`}>
            <div className="flex items-center gap-3">
              <StatusDot status={it.key} size="h-8 w-8" />
              <div>
                <div className="text-3xl font-bold">{summary?.[it.key] ?? 0}</div>
                <div className="text-sm text-slate-500">{it.label}</div>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function EquipmentCard({ eq }) {
  const meta = statusMeta(eq.status);
  const due =
    eq.days_until_due == null
      ? "No service due"
      : eq.days_until_due < 0
      ? `Overdue ${Math.abs(eq.days_until_due)}d`
      : `Due in ${eq.days_until_due}d`;
  return (
    <Link to={`/equipment/${eq.id}`}>
      <Card className={`border-l-8 ${meta.border} transition hover:shadow-md`}>
        <div className="flex items-start justify-between">
          <div>
            <div className="font-mono text-lg font-bold">{eq.equipment_code}</div>
            <div className="text-sm text-slate-600">{eq.name || "—"}</div>
            <div className="mt-1 text-xs uppercase tracking-wide text-slate-400">
              {eq.category || "uncategorized"}
            </div>
          </div>
          <StatusDot status={eq.status} size="h-7 w-7" />
        </div>
        <div className="mt-4 flex items-center justify-between">
          <StateBadge state={eq.current_state} />
          <span className={`text-sm font-semibold ${meta.text}`}>{due}</span>
        </div>
      </Card>
    </Link>
  );
}

export default function Dashboard() {
  const { data, error, refresh } = usePolling(api.listEquipment, 5000);
  const [statusFilter, setStatusFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [recomputing, setRecomputing] = useState(false);

  const equipment = data?.equipment || [];
  const categories = useMemo(
    () => [...new Set(equipment.map((e) => e.category).filter(Boolean))],
    [equipment]
  );

  const filtered = equipment.filter(
    (e) =>
      (statusFilter === "all" || e.status === statusFilter) &&
      (stateFilter === "all" || e.current_state === stateFilter) &&
      (categoryFilter === "all" || e.category === categoryFilter)
  );

  async function doRecompute() {
    setRecomputing(true);
    try {
      await api.recompute();
      await refresh();
    } finally {
      setRecomputing(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Fleet Dashboard</h1>
        <button
          onClick={doRecompute}
          disabled={recomputing}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {recomputing ? "Recomputing…" : "Recompute status"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-100 px-4 py-3 text-sm text-red-800">
          Could not reach API: {error}
        </div>
      )}

      <SummaryBar summary={data?.summary} />

      <div className="flex flex-wrap gap-3">
        <Filter label="Status" value={statusFilter} onChange={setStatusFilter}
          options={["all", "green", "orange", "red"]} />
        <Filter label="State" value={stateFilter} onChange={setStateFilter}
          options={["all", "available", "rented", "sold", "in_service"]} />
        <Filter label="Category" value={categoryFilter} onChange={setCategoryFilter}
          options={["all", ...categories]} />
        <span className="ml-auto self-center text-xs text-slate-400">
          Live — polling every 5s
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((eq) => (
          <EquipmentCard key={eq.id} eq={eq} />
        ))}
      </div>
      {filtered.length === 0 && (
        <div className="rounded-lg bg-white p-8 text-center text-slate-400">
          No equipment. Seed the database or upload a document.
        </div>
      )}
    </div>
  );
}

function Filter({ label, value, onChange, options }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-slate-300 bg-white px-2 py-1"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {String(o).replace("_", " ")}
          </option>
        ))}
      </select>
    </label>
  );
}
