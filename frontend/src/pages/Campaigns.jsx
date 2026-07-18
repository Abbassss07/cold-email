import { useEffect, useState } from "react";
import { listCampaigns } from "@/lib/api";
import { History } from "lucide-react";

export default function Campaigns() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { const { data } = await listCampaigns(); setRows(data); }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Campaign History</h1>
        <p className="text-sm text-slate-500 mt-1.5">Every send is logged here for auditability.</p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-[0_2px_10px_rgba(0,0,0,0.04)]">
        {loading ? (
          <div className="p-10 text-center text-slate-500 text-sm">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-14 text-center" data-testid="campaigns-empty">
            <div className="w-12 h-12 mx-auto rounded-2xl bg-slate-100 text-slate-500 flex items-center justify-center mb-4">
              <History size={22} strokeWidth={1.6} />
            </div>
            <div className="text-base font-semibold text-slate-900">No campaigns yet</div>
            <div className="text-sm text-slate-500 mt-1">Send a newsletter to create your first campaign record.</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <Th>Date</Th><Th>Name</Th><Th>Kind</Th><Th>Sender</Th><Th>List</Th>
                  <Th className="text-right">Total</Th><Th className="text-right">Sent</Th><Th className="text-right">Failed</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id} className="border-b border-slate-100 hover:bg-slate-50/60">
                    <Td className="font-mono text-xs">{new Date(c.started_at).toLocaleString()}</Td>
                    <Td className="font-medium text-slate-900">{c.name}</Td>
                    <Td><span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border bg-blue-50 text-[#2563EB] border-blue-100">{c.kind}</span></Td>
                    <Td className="font-mono text-xs">{c.from_email}</Td>
                    <Td>{c.list_name || "—"}</Td>
                    <Td className="text-right tabular-nums">{c.total}</Td>
                    <Td className="text-right tabular-nums text-emerald-700 font-medium">{c.sent}</Td>
                    <Td className="text-right tabular-nums text-red-700">{c.failed}</Td>
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

const Th = ({ children, className = "" }) => <th className={`px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider ${className}`}>{children}</th>;
const Td = ({ children, className = "" }) => <td className={`px-6 py-4 text-sm text-slate-700 ${className}`}>{children}</td>;
