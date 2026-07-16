import { Link } from "react-router-dom";
import { api } from "../api";
import { usePolling } from "../hooks";
import { Card, LevelChip } from "../components/ui";

export default function Notifications() {
  const { data, error } = usePolling(api.listNotifications, 5000);
  const items = data || [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Notification Feed</h1>

      {error && (
        <div className="rounded bg-red-100 px-4 py-3 text-sm text-red-800">{error}</div>
      )}

      {items.length === 0 ? (
        <Card className="text-center text-slate-400">No alerts yet.</Card>
      ) : (
        <div className="space-y-2">
          {items.map((n) => (
            <Card
              key={n.id}
              className={`border-l-8 ${
                n.level === "critical" ? "border-status-red" : "border-status-orange"
              }`}
            >
              <div className="flex items-center gap-3">
                <LevelChip level={n.level} />
                <Link
                  to={`/equipment/${n.equipment_id}`}
                  className="flex-1 font-medium hover:underline"
                >
                  {n.message}
                </Link>
                <span className="text-xs text-slate-400">
                  {new Date(n.sent_at).toLocaleString()}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
