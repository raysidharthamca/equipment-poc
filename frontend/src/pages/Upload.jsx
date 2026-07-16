import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Card, DocTypeBadge, StatusDot } from "../components/ui";

export default function Upload() {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | extracting | done | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef();

  async function handleFile(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF.");
      setStatus("error");
      return;
    }
    setStatus("extracting");
    setError(null);
    setResult(null);
    try {
      const res = await api.upload(file);
      setResult(res);
      setStatus("done");
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Upload Document</h1>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFile(e.dataTransfer.files[0]);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition ${
          dragging ? "border-slate-800 bg-slate-50" : "border-slate-300 bg-white"
        }`}
      >
        <div className="text-4xl">📄</div>
        <p className="mt-3 font-semibold">Drag & drop a PDF here</p>
        <p className="text-sm text-slate-400">or click to browse</p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => handleFile(e.target.files[0])}
        />
      </div>

      {status === "extracting" && (
        <Card className="flex items-center gap-3">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-800" />
          <span>Claude is classifying and extracting the document…</span>
        </Card>
      )}

      {status === "error" && (
        <div className="rounded-lg bg-red-100 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {status === "done" && result && <Result result={result} />}
    </div>
  );
}

function Result({ result }) {
  const doc = result.document;
  return (
    <div className="space-y-4">
      <Card className="border-l-8 border-emerald-500">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-semibold">Extraction complete</div>
            <div className="text-sm text-slate-500">{doc.filename}</div>
          </div>
          <div className="flex items-center gap-2">
            <DocTypeBadge type={doc.doc_type} />
            <span className="text-sm text-slate-500">
              conf {doc.extraction_confidence?.toFixed?.(2) ?? "—"}
            </span>
            {doc.needs_review && (
              <span className="rounded bg-orange-100 px-2 py-0.5 text-xs font-bold text-orange-800">
                REVIEW
              </span>
            )}
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
          Extracted fields
        </h2>
        <pre className="max-h-72 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
          {JSON.stringify(result.extraction, null, 2)}
        </pre>
      </Card>

      {result.status_changes?.length > 0 && (
        <Card>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
            Status changes
          </h2>
          <ul className="space-y-1 text-sm">
            {result.status_changes.map((c, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="font-mono">{c.equipment_code}</span>
                <StatusDot status={c.old} size="h-4 w-4" />
                <span>→</span>
                <StatusDot status={c.new} size="h-4 w-4" />
                <span className="text-slate-500">
                  {c.days_until_due == null ? "" : `(${c.days_until_due}d)`}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {result.affected_equipment?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {result.affected_equipment.map((e) => (
            <Link
              key={e.id}
              to={`/equipment/${e.id}`}
              className="rounded-lg bg-white px-3 py-2 text-sm font-mono shadow-sm hover:shadow"
            >
              {e.equipment_code} →
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
