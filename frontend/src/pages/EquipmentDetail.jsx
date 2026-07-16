import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { usePolling } from "../hooks";
import { Card, DocTypeBadge, LevelChip, StateBadge, StatusDot, statusMeta } from "../components/ui";

function Section({ title, children }) {
  return (
    <Card>
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
        {title}
      </h2>
      {children}
    </Card>
  );
}

function money(amount, currency) {
  if (amount == null) return "—";
  return `${amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} ${currency || ""}`.trim();
}

export default function EquipmentDetail() {
  const { id } = useParams();
  const { data: eq, error } = usePolling(() => api.getEquipment(id), 5000, [id]);

  if (error)
    return <div className="rounded bg-red-100 p-4 text-red-800">Error: {error}</div>;
  if (!eq) return <div className="text-slate-400">Loading…</div>;

  const meta = statusMeta(eq.status);

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm text-slate-500 hover:underline">
        ← Back to dashboard
      </Link>

      <Card className={`border-l-8 ${meta.border}`}>
        <div className="flex items-start justify-between">
          <div>
            <div className="font-mono text-2xl font-bold">{eq.equipment_code}</div>
            <div className="text-slate-600">{eq.name || "—"}</div>
            <div className="mt-2 flex items-center gap-2">
              <StateBadge state={eq.current_state} />
              <span className="text-xs uppercase tracking-wide text-slate-400">
                {eq.category || "uncategorized"}
              </span>
            </div>
          </div>
          <div className="text-right">
            <StatusDot status={eq.status} size="h-10 w-10" />
            <div className={`mt-2 text-sm font-semibold ${meta.text}`}>
              {eq.status_explanation}
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Section title="Specifications">
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <Field k="Manufacture date" v={eq.manufacture_date} />
            <Field k="Service interval" v={`${eq.service_interval_days} days`} />
            <Field k="Last service" v={eq.last_service_date} />
            <Field
              k="Days until due"
              v={eq.days_until_due == null ? "—" : eq.days_until_due}
            />
          </dl>
          {eq.notes && (
            <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
              {eq.notes}
            </p>
          )}
        </Section>

        <Section title="Linked Source Documents">
          {eq.documents.length === 0 ? (
            <p className="text-sm text-slate-400">None</p>
          ) : (
            <ul className="space-y-2">
              {eq.documents.map((d) => (
                <li key={d.id} className="flex items-center justify-between text-sm">
                  <a
                    href={api.fileUrl(d.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-700 hover:underline"
                  >
                    {d.filename}
                  </a>
                  <span className="flex items-center gap-2">
                    {d.needs_review && (
                      <span className="text-xs font-bold text-status-orange">REVIEW</span>
                    )}
                    <DocTypeBadge type={d.doc_type} />
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-slate-400">
            Every field on this page traces back to a source PDF (auditability).
          </p>
        </Section>
      </div>

      <Section title="Transaction History">
        <Timeline
          items={eq.transactions}
          render={(t) => ({
            date: t.transaction_date,
            title: t.type.replace("_", " "),
            detail: `${t.customer_name || ""} ${
              t.due_back_date ? `• due back ${t.due_back_date}` : ""
            } • ${money(t.amount, t.currency)}`,
            docId: t.document_id,
          })}
        />
      </Section>

      <Section title="Service History">
        <Timeline
          items={eq.service_records}
          render={(s) => ({
            date: s.service_date,
            title: s.service_type || "Service",
            detail: `${s.technician || "—"} ${
              s.next_due_date ? `• next due ${s.next_due_date}` : ""
            }${s.findings ? ` — ${s.findings}` : ""}`,
            docId: s.document_id,
          })}
        />
      </Section>

      <Section title="Notifications">
        {eq.notifications.length === 0 ? (
          <p className="text-sm text-slate-400">None</p>
        ) : (
          <ul className="space-y-2">
            {eq.notifications.map((n) => (
              <li key={n.id} className="flex items-center gap-3 text-sm">
                <LevelChip level={n.level} />
                <span className="flex-1">{n.message}</span>
                <span className="text-xs text-slate-400">
                  {n.channel} • {new Date(n.sent_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

function Field({ k, v }) {
  return (
    <>
      <dt className="text-slate-500">{k}</dt>
      <dd className="font-medium">{v ?? "—"}</dd>
    </>
  );
}

function Timeline({ items, render }) {
  if (!items || items.length === 0)
    return <p className="text-sm text-slate-400">None</p>;
  return (
    <ol className="space-y-3">
      {items.map((it, i) => {
        const r = render(it);
        return (
          <li key={i} className="flex gap-3">
            <div className="mt-1 h-3 w-3 shrink-0 rounded-full bg-slate-400" />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">{r.date || "—"}</span>
                <span className="font-semibold capitalize">{r.title}</span>
                {r.docId && (
                  <a
                    href={api.fileUrl(r.docId)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    source
                  </a>
                )}
              </div>
              <div className="text-sm text-slate-600">{r.detail}</div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
