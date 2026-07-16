import { useState } from "react";
import { api } from "../api";
import { usePolling } from "../hooks";
import { Card, DocTypeBadge } from "../components/ui";

export default function ReviewQueue() {
  const { data, error, refresh } = usePolling(api.reviewQueue, 8000);
  const items = data || [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Review Queue</h1>
      <p className="text-sm text-slate-500">
        Low-confidence extractions get a human check before they're trusted.
      </p>

      {error && (
        <div className="rounded bg-red-100 px-4 py-3 text-sm text-red-800">{error}</div>
      )}

      {items.length === 0 ? (
        <Card className="text-center text-slate-400">
          Nothing to review — the queue is clear. 🎉
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((doc) => (
            <ReviewItem key={doc.id} doc={doc} onDone={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}

function ReviewItem({ doc, onDone }) {
  const [approving, setApproving] = useState(false);

  async function approve() {
    setApproving(true);
    try {
      await api.approve(doc.id, {});
      await onDone();
    } finally {
      setApproving(false);
    }
  }

  let parsed = null;
  try {
    parsed = doc.raw_extraction_json ? JSON.parse(doc.raw_extraction_json) : null;
  } catch {
    parsed = null;
  }

  return (
    <Card className="border-l-8 border-status-orange">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-semibold">{doc.filename}</div>
          <div className="mt-1 flex items-center gap-2">
            <DocTypeBadge type={doc.doc_type} />
            <span className="text-sm text-slate-500">
              confidence {doc.extraction_confidence?.toFixed?.(2) ?? "—"}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={api.fileUrl(doc.id)}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50"
          >
            View source PDF
          </a>
          <button
            onClick={approve}
            disabled={approving}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {approving ? "Approving…" : "Approve"}
          </button>
        </div>
      </div>
      <pre className="mt-3 max-h-56 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
        {parsed ? JSON.stringify(parsed, null, 2) : doc.raw_extraction_json || "(no data)"}
      </pre>
    </Card>
  );
}
