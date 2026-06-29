import { useEffect, useMemo, useState } from "react";
import { Eye, Sparkles, Send, Trash2, RefreshCw, Mail, Inbox } from "lucide-react";
import { toast } from "sonner";
import StatsCard from "@/components/StatsCard";
import UploadZone from "@/components/UploadZone";
import StatusBadge from "@/components/StatusBadge";
import EmailEditDialog from "@/components/EmailEditDialog";
import {
  deleteEmail,
  generate,
  getStats,
  listEmails,
  regenerate,
  sendEmails,
} from "@/lib/api";

export default function Dashboard() {
  const [emails, setEmails] = useState([]);
  const [stats, setStats] = useState({ pending: 0, generated: 0, sent: 0, failed: 0, total: 0 });
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [genProgress, setGenProgress] = useState(null); // {current,total}
  const [sendProgress, setSendProgress] = useState(null);
  const [editTarget, setEditTarget] = useState(null);
  const [skipped, setSkipped] = useState([]);

  const refresh = async () => {
    try {
      const [{ data: rows }, { data: s }] = await Promise.all([listEmails(), getStats()]);
      setEmails(rows);
      setStats(s);
    } catch (e) {
      toast.error("Failed to load emails");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const allChecked = useMemo(
    () => emails.length > 0 && emails.every((e) => selected.has(e.id)),
    [emails, selected]
  );

  const toggleAll = () => {
    if (allChecked) setSelected(new Set());
    else setSelected(new Set(emails.map((e) => e.id)));
  };

  const toggleOne = (id) => {
    const s = new Set(selected);
    if (s.has(id)) s.delete(id);
    else s.add(id);
    setSelected(s);
  };

  const onImported = (data) => {
    setSkipped(data.skipped || []);
    refresh();
  };

  const runGenerate = async (ids) => {
    if (ids.length === 0) {
      toast.error("Select at least one row to generate");
      return;
    }
    setGenProgress({ current: 0, total: ids.length });
    // sequential to allow visible progress
    for (let i = 0; i < ids.length; i++) {
      try {
        await generate([ids[i]]);
      } catch (e) {
        toast.error(e?.response?.data?.detail || "Generation error");
      }
      setGenProgress({ current: i + 1, total: ids.length });
    }
    setGenProgress(null);
    toast.success("Generation complete");
    refresh();
  };

  const runSend = async (ids) => {
    if (ids.length === 0) {
      toast.error("Select at least one row to send");
      return;
    }
    setSendProgress({ current: 0, total: ids.length });
    for (let i = 0; i < ids.length; i++) {
      try {
        await sendEmails([ids[i]]);
      } catch (e) {
        toast.error(e?.response?.data?.detail || "Send error");
      }
      setSendProgress({ current: i + 1, total: ids.length });
    }
    setSendProgress(null);
    toast.success("Send batch complete");
    refresh();
  };

  const onDelete = async (id) => {
    if (!window.confirm("Delete this email?")) return;
    try {
      await deleteEmail(id);
      toast.success("Deleted");
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const onRegen = async (id) => {
    try {
      await regenerate(id);
      toast.success("Regenerated");
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Regeneration failed");
    }
  };

  const selectedIds = [...selected];
  const generatableIds = selectedIds.filter((id) => {
    const r = emails.find((e) => e.id === id);
    return r && (r.status === "pending" || r.status === "failed" || r.status === "generated");
  });
  const sendableIds = selectedIds.filter((id) => {
    const r = emails.find((e) => e.id === id);
    return r && r.status === "generated";
  });

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1.5">
            Upload, personalize and send cold outreach — one polished workflow.
          </p>
        </div>
        <div className="text-xs text-slate-500">
          Daily sent: <span className="font-semibold tabular-nums text-slate-900">{stats.daily_sent || 0}</span>
          <span className="text-slate-400"> / {stats.daily_limit || 200}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard label="Today" value={stats.today || 0} testId="stat-today" />
        <StatsCard label="Generated" value={stats.generated} accent="blue" testId="stat-generated" />
        <StatsCard label="Sent" value={stats.sent} accent="green" testId="stat-sent" />
        <StatsCard label="Failed" value={stats.failed} accent="red" testId="stat-failed" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard label="Pending" value={stats.pending} accent="amber" testId="stat-pending" />
        <StatsCard label="Drafts" value={stats.draft || 0} testId="stat-draft" />
        <StatsCard label="Success rate" value={`${stats.success_rate || 0}%`} accent="green" testId="stat-success-rate" />
        <StatsCard label="Avg gen time" value={`${((stats.avg_gen_ms || 0) / 1000).toFixed(1)}s`} accent="blue" testId="stat-avg-gen" />
      </div>

      <UploadZone onImported={onImported} />

      {skipped.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 text-sm text-amber-800">
          <div className="font-semibold mb-1.5">Skipped {skipped.length} row(s)</div>
          <ul className="list-disc pl-5 space-y-0.5">
            {skipped.slice(0, 6).map((r, i) => (
              <li key={i}>Row {r.row}: {r.reason}</li>
            ))}
            {skipped.length > 6 && <li>+ {skipped.length - 6} more…</li>}
          </ul>
        </div>
      )}

      {(genProgress || sendProgress) && (
        <ProgressBlock label={genProgress ? "Generating emails" : "Sending emails"}
                       progress={genProgress || sendProgress} />
      )}

      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => runGenerate(generatableIds.length ? generatableIds : emails.filter(e => e.status === "pending").map(e => e.id))}
          disabled={!!genProgress}
          data-testid="btn-generate-selected"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-[#2563EB] hover:bg-[#1D4ED8] text-white transition-all hover:-translate-y-[1px] hover:shadow-md hover:shadow-blue-500/20 disabled:opacity-50"
        >
          <Sparkles size={16} strokeWidth={1.6} /> Generate {selected.size > 0 ? `(${generatableIds.length})` : "all pending"}
        </button>
        <button
          onClick={() => runSend(sendableIds)}
          disabled={!!sendProgress || sendableIds.length === 0}
          data-testid="btn-send-selected"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 transition-all disabled:opacity-50"
        >
          <Send size={16} strokeWidth={1.6} /> Send selected ({sendableIds.length})
        </button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-[0_2px_10px_rgba(0,0,0,0.04)]">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm">Loading…</div>
        ) : emails.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-5 py-3 text-left w-10">
                    <input type="checkbox" checked={allChecked} onChange={toggleAll}
                           data-testid="select-all-checkbox" />
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Company</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Contact</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Subject</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {emails.map((e) => (
                  <tr key={e.id} className="border-b border-slate-100 hover:bg-slate-50/60 transition-colors" data-testid={`email-row-${e.id}`}>
                    <td className="px-5 py-4">
                      <input type="checkbox" checked={selected.has(e.id)} onChange={() => toggleOne(e.id)}
                             data-testid={`row-checkbox-${e.id}`} />
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-slate-900">
                      <div>{e.company_name}</div>
                      {e.industry && <div className="text-[11px] text-slate-400 mt-0.5">{e.industry}</div>}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      {e.contact_name && <div className="font-medium text-slate-800">{e.contact_name}</div>}
                      <div className="font-mono text-xs text-slate-500">{e.contact_email}</div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-700 max-w-md truncate">{e.subject || <span className="text-slate-400 italic">— not generated —</span>}</td>
                    <td className="px-6 py-4"><StatusBadge status={e.status} /></td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1 justify-end">
                        <IconBtn title="Preview / Edit" onClick={() => setEditTarget(e)} data-testid={`btn-edit-${e.id}`}><Eye size={16} strokeWidth={1.6} /></IconBtn>
                        <IconBtn title="Regenerate" onClick={() => onRegen(e.id)} data-testid={`btn-regen-${e.id}`}><RefreshCw size={16} strokeWidth={1.6} /></IconBtn>
                        <IconBtn title="Delete" onClick={() => onDelete(e.id)} data-testid={`btn-delete-${e.id}`}><Trash2 size={16} strokeWidth={1.6} /></IconBtn>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <EmailEditDialog
        open={!!editTarget}
        email={editTarget}
        onClose={() => setEditTarget(null)}
        onChanged={refresh}
      />
    </div>
  );
}

function IconBtn({ children, ...props }) {
  return (
    <button
      {...props}
      className="w-8 h-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
    >
      {children}
    </button>
  );
}

function ProgressBlock({ label, progress }) {
  const pct = progress.total ? Math.round((progress.current / progress.total) * 100) : 0;
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-[0_2px_10px_rgba(0,0,0,0.04)]" data-testid="progress-block">
      <div className="flex items-center justify-between text-sm mb-2.5">
        <div className="font-medium text-slate-900">{label}…</div>
        <div className="text-slate-500 tabular-nums">{progress.current} / {progress.total}</div>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
        <div className="bg-[#2563EB] h-2 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="p-14 text-center" data-testid="empty-state">
      <div className="w-12 h-12 mx-auto rounded-2xl bg-slate-100 text-slate-500 flex items-center justify-center mb-4">
        <Inbox size={22} strokeWidth={1.6} />
      </div>
      <div className="text-base font-semibold text-slate-900">No companies yet</div>
      <div className="text-sm text-slate-500 mt-1">Upload a CSV above to get started.</div>
    </div>
  );
}
