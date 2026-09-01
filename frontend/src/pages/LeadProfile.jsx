import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Plus, Check } from "lucide-react";
import {
  createMeeting, createTask, getCrmMeta, getLead, getLeadTimeline,
  listMeetings, listTasks, updateLead, updateTask,
} from "@/lib/api";

const stageLabel = (s) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const serviceLabel = (s) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function LeadProfile() {
  const { id } = useParams();
  const nav = useNavigate();
  const [lead, setLead] = useState(null);
  const [meta, setMeta] = useState({ stages: [], services: [] });
  const [timeline, setTimeline] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [newTask, setNewTask] = useState({ title: "", due_date: "" });
  const [newMeeting, setNewMeeting] = useState({ date: "", time: "", outcome: "", notes: "", next_action: "" });

  const loadAll = useCallback(async () => {
    const [l, m, t, ts, ms] = await Promise.all([
      getLead(id), getCrmMeta(), getLeadTimeline(id),
      listTasks({ lead_id: id }), listMeetings(id),
    ]);
    setLead(l.data); setMeta(m.data); setTimeline(t.data); setTasks(ts.data); setMeetings(ms.data);
  }, [id]);
  useEffect(() => { loadAll().catch(() => toast.error("Failed to load")); }, [loadAll]);

  if (!lead) return <div className="p-10 text-slate-500 text-sm">Loading…</div>;

  const patch = async (data) => {
    try {
      await updateLead(id, data);
      toast.success("Saved");
      loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };

  const toggleService = (s) => {
    const cur = new Set(lead.services || []);
    if (cur.has(s)) cur.delete(s); else cur.add(s);
    patch({ services: [...cur] });
  };

  const addTask = async () => {
    if (!newTask.title) return;
    try {
      await createTask({ lead_id: id, ...newTask });
      setNewTask({ title: "", due_date: "" });
      loadAll();
    } catch (e) { toast.error("Failed to add task"); }
  };

  const completeTask = async (tid) => {
    await updateTask(tid, { status: "completed" });
    loadAll();
  };

  const addMeeting = async () => {
    if (!newMeeting.date) return;
    try {
      await createMeeting({ lead_id: id, ...newMeeting });
      setNewMeeting({ date: "", time: "", outcome: "", notes: "", next_action: "" });
      loadAll();
    } catch (e) { toast.error("Failed to add meeting"); }
  };

  return (
    <div className="space-y-6 fade-in" data-testid="lead-profile-page">
      <button onClick={() => nav(-1)} className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900" data-testid="back-btn">
        <ArrowLeft size={16} /> Back
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">{lead.company_name}</h1>
          <div className="text-sm text-slate-500 mt-1">
            {lead.contact_name && <span className="font-medium text-slate-700">{lead.contact_name} · </span>}
            <span className="font-mono text-xs">{lead.contact_email}</span>
            {lead.industry && <> · {lead.industry}</>}
          </div>
        </div>
        <select
          value={lead.stage || "new_lead"}
          onChange={(e) => patch({ stage: e.target.value })}
          data-testid="stage-select"
          className="bg-white border border-slate-200 rounded-xl px-3 py-2 text-sm font-medium focus:border-[#2563EB] outline-none"
        >
          {meta.stages.map((s) => <option key={s} value={s}>{stageLabel(s)}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card title="Service requirements">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {meta.services.map((s) => {
                const on = (lead.services || []).includes(s);
                return (
                  <label key={s} className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm cursor-pointer transition-all ${on ? "bg-blue-50 border-[#2563EB] text-[#2563EB] font-medium" : "bg-white border-slate-200 text-slate-700 hover:border-slate-300"}`} data-testid={`service-${s}`}>
                    <input type="checkbox" checked={on} onChange={() => toggleService(s)} className="accent-[#2563EB]" />
                    {serviceLabel(s)}
                  </label>
                );
              })}
            </div>
          </Card>

          <Card title="Timeline">
            {timeline.length === 0 ? (
              <div className="text-sm text-slate-500">No events yet.</div>
            ) : (
              <ol className="relative border-l border-slate-200 pl-6 space-y-4">
                {timeline.map((e) => (
                  <li key={e.id} className="relative">
                    <span className="absolute -left-[26px] top-1.5 w-2.5 h-2.5 rounded-full bg-[#2563EB]" />
                    <div className="text-sm font-medium text-slate-900">{e.title}</div>
                    {e.detail && <div className="text-xs text-slate-500 mt-0.5">{e.detail}</div>}
                    <div className="text-[11px] font-mono text-slate-400 mt-1">{new Date(e.at).toLocaleString()}</div>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          <Card title="Meetings">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3">
              <input type="date" value={newMeeting.date} onChange={(e) => setNewMeeting({ ...newMeeting, date: e.target.value })} data-testid="meeting-date" className="col-span-1 border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-[#2563EB]" />
              <input placeholder="Time" value={newMeeting.time} onChange={(e) => setNewMeeting({ ...newMeeting, time: e.target.value })} className="col-span-1 border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-[#2563EB]" />
              <input placeholder="Outcome" value={newMeeting.outcome} onChange={(e) => setNewMeeting({ ...newMeeting, outcome: e.target.value })} className="col-span-2 border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-[#2563EB]" />
              <button onClick={addMeeting} data-testid="add-meeting-btn" className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl px-3 py-2 text-sm font-medium">Add</button>
            </div>
            {meetings.length === 0 ? (
              <div className="text-sm text-slate-500">No meetings yet.</div>
            ) : (
              <ul className="space-y-2">
                {meetings.map((m) => (
                  <li key={m.id} className="text-sm border border-slate-200 rounded-xl px-3 py-2">
                    <div className="font-medium">{m.date} {m.time}</div>
                    {m.outcome && <div className="text-slate-600">{m.outcome}</div>}
                    {m.notes && <div className="text-xs text-slate-500 mt-1">{m.notes}</div>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Details">
            <Row label="Country" value={lead.country} onSave={(v) => patch({ country: v })} />
            <Row label="Phone" value={lead.phone} onSave={(v) => patch({ phone: v })} />
            <Row label="Website" value={lead.website} readOnly />
            <Row label="Industry" value={lead.industry} readOnly />
            <Row label="Last contact" value={lead.last_contact_at ? new Date(lead.last_contact_at).toLocaleString() : "—"} readOnly />
          </Card>

          <Card title="Internal notes">
            <textarea
              rows={5}
              defaultValue={lead.internal_notes || ""}
              onBlur={(e) => patch({ internal_notes: e.target.value })}
              placeholder="Only visible inside the CRM…"
              data-testid="internal-notes"
              className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-[#2563EB]"
            />
          </Card>

          <Card title="Tasks">
            <div className="flex gap-2 mb-3">
              <input placeholder="Task title" value={newTask.title} onChange={(e) => setNewTask({ ...newTask, title: e.target.value })} data-testid="task-title" className="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-[#2563EB]" />
              <input type="date" value={newTask.due_date} onChange={(e) => setNewTask({ ...newTask, due_date: e.target.value })} data-testid="task-due" className="border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-[#2563EB]" />
              <button onClick={addTask} data-testid="add-task-btn" className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl px-3 py-2 text-sm font-medium"><Plus size={14} /></button>
            </div>
            {tasks.length === 0 ? (
              <div className="text-sm text-slate-500">No tasks.</div>
            ) : (
              <ul className="space-y-2">
                {tasks.map((t) => (
                  <li key={t.id} className="flex items-center gap-2 text-sm">
                    <button onClick={() => completeTask(t.id)} className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${t.status === "completed" ? "bg-emerald-500 border-emerald-500 text-white" : "border-slate-300 hover:border-[#2563EB]"}`} data-testid={`complete-${t.id}`}>
                      {t.status === "completed" && <Check size={12} strokeWidth={3} />}
                    </button>
                    <span className={`flex-1 ${t.status === "completed" ? "line-through text-slate-400" : t.status === "overdue" ? "text-red-600" : "text-slate-800"}`}>{t.title}</span>
                    {t.due_date && <span className="text-xs font-mono text-slate-400">{t.due_date}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-5">
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 mb-3">{title}</div>
      {children}
    </div>
  );
}

function Row({ label, value, onSave, readOnly }) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState(value || "");
  useEffect(() => setV(value || ""), [value]);
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 border-b border-slate-100 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      {readOnly ? (
        <span className="text-sm text-slate-800 truncate">{value || "—"}</span>
      ) : editing ? (
        <input
          autoFocus
          value={v}
          onChange={(e) => setV(e.target.value)}
          onBlur={() => { setEditing(false); if (v !== value) onSave(v); }}
          onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); }}
          className="text-sm border-b border-[#2563EB] outline-none text-right w-32"
        />
      ) : (
        <button onClick={() => setEditing(true)} className="text-sm text-slate-800 hover:text-[#2563EB]">{value || "—"}</button>
      )}
    </div>
  );
}
