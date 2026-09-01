import { useEffect, useState } from "react";
import { Download, Search } from "lucide-react";
import { exportLogsUrl, getLogs } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

export default function Logs() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  // re-fetch when filters change with small debounce
  useEffect(() => {
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await getLogs({ q: q || undefined, status: status || undefined });
        setRows(data);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q, status]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Logs</h1>
        <p className="text-sm text-slate-500 mt-1.5">Every send attempt is recorded here for traceability.</p>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search size={16} strokeWidth={1.6} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            data-testid="logs-search-input"
            placeholder="Search company, email or subject…"
            className="w-full bg-white border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          data-testid="logs-status-filter"
          className="bg-white border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:border-[#2563EB] outline-none"
        >
          <option value="">All statuses</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
        </select>
        <a
          href={exportLogsUrl}
          data-testid="logs-export-link"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 transition-all ml-auto"
        >
          <Download size={16} strokeWidth={1.6} /> Export CSV
        </a>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-[0_2px_10px_rgba(0,0,0,0.04)]">
        {loading ? (
          <div className="p-10 text-center text-slate-500 text-sm">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm" data-testid="logs-empty">No log entries yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <Th>Time</Th>
                  <Th>Company</Th>
                  <Th>Email</Th>
                  <Th>Subject</Th>
                  <Th>Status</Th>
                  <Th>Message ID</Th>
                  <Th>Error</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100 hover:bg-slate-50/60">
                    <Td className="font-mono text-xs">{new Date(r.timestamp).toLocaleString()}</Td>
                    <Td className="font-medium text-slate-900">{r.company_name}</Td>
                    <Td className="text-xs font-mono">{r.contact_email}</Td>
                    <Td className="max-w-xs truncate">{r.subject}</Td>
                    <Td><StatusBadge status={r.status} /></Td>
                    <Td className="font-mono text-xs text-slate-500 max-w-[200px] truncate">{r.message_id || "—"}</Td>
                    <Td className="text-xs text-red-600 max-w-xs truncate">{r.error || "—"}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

const Th = ({ children }) => (
  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{children}</th>
);
const Td = ({ children, className = "" }) => (
  <td className={`px-6 py-4 text-sm text-slate-700 ${className}`}>{children}</td>
);
