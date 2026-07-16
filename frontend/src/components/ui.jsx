// Shared presentational bits. Status colors must be unmistakable at projector
// distance — large dots, colored card borders.

const STATUS = {
  green: { dot: "bg-status-green", border: "border-status-green", text: "text-status-green", label: "Green" },
  orange: { dot: "bg-status-orange", border: "border-status-orange", text: "text-status-orange", label: "Orange" },
  red: { dot: "bg-status-red", border: "border-status-red", text: "text-status-red", label: "Red" },
};

export function StatusDot({ status, size = "h-6 w-6" }) {
  const s = STATUS[status] || STATUS.green;
  return <span className={`inline-block rounded-full ${size} ${s.dot} shadow`} />;
}

export function statusMeta(status) {
  return STATUS[status] || STATUS.green;
}

const STATE_STYLE = {
  available: "bg-emerald-100 text-emerald-800",
  rented: "bg-blue-100 text-blue-800",
  sold: "bg-slate-200 text-slate-700",
  in_service: "bg-amber-100 text-amber-800",
};

export function StateBadge({ state }) {
  const cls = STATE_STYLE[state] || "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>
      {String(state || "").replace("_", " ")}
    </span>
  );
}

const LEVEL_STYLE = {
  warning: "border-status-orange bg-orange-50 text-orange-900",
  critical: "border-status-red bg-red-50 text-red-900",
};

export function LevelChip({ level }) {
  const cls = LEVEL_STYLE[level] || "border-slate-300 bg-slate-50 text-slate-700";
  return (
    <span className={`rounded border px-2 py-0.5 text-xs font-bold uppercase ${cls}`}>
      {level}
    </span>
  );
}

export function DocTypeBadge({ type }) {
  return (
    <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-medium text-white">
      {String(type || "unknown").replace(/_/g, " ")}
    </span>
  );
}

export function Card({ children, className = "" }) {
  return (
    <div className={`rounded-xl bg-white p-5 shadow-sm ${className}`}>{children}</div>
  );
}
