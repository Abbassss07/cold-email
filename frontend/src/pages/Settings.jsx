import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, XCircle } from "lucide-react";
import {
  changePassword,
  getSettings,
  updateContext,
  updateDailyLimit,
} from "@/lib/api";

export default function Settings() {
  const [data, setData] = useState(null);
  const [context, setContext] = useState("");
  const [limit, setLimit] = useState(200);
  const [pw, setPw] = useState({ current: "", next: "" });
  const [savingCtx, setSavingCtx] = useState(false);
  const [savingLimit, setSavingLimit] = useState(false);
  const [savingPw, setSavingPw] = useState(false);

  const load = async () => {
    const { data: s } = await getSettings();
    setData(s);
    setContext(s.company_context);
    setLimit(s.daily_limit);
  };

  useEffect(() => { load(); }, []);

  const saveContext = async () => {
    setSavingCtx(true);
    try {
      await updateContext(context);
      toast.success("Company context updated");
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    finally { setSavingCtx(false); }
  };

  const saveLimit = async () => {
    setSavingLimit(true);
    try {
      await updateDailyLimit(Number(limit));
      toast.success("Daily limit updated");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    finally { setSavingLimit(false); }
  };

  const savePw = async () => {
    if (!pw.current || pw.next.length < 6) {
      toast.error("Enter current password and a new one of 6+ chars");
      return;
    }
    setSavingPw(true);
    try {
      await changePassword(pw.current, pw.next);
      toast.success("Password updated");
      setPw({ current: "", next: "" });
    } catch (e) { toast.error(e?.response?.data?.detail || "Update failed"); }
    finally { setSavingPw(false); }
  };

  if (!data) return <div className="p-10 text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500 mt-1.5">Manage authentication, sending limits, and AI context.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Provider status">
          <ProviderRow label="Gemini API" ok={data.gemini_configured} />
          <ProviderRow label="Resend API" ok={data.resend.configured} />
          <div className="mt-3 text-xs text-slate-500">
            From: <span className="font-mono">{data.from_name} &lt;{data.from_email}&gt;</span>
          </div>
        </Card>

        <Card title="Daily send limit">
          <input
            type="number"
            min={1}
            max={5000}
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            data-testid="settings-daily-limit"
            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
          <button
            onClick={saveLimit}
            disabled={savingLimit}
            data-testid="settings-save-limit"
            className="mt-3 w-full bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-all hover:-translate-y-[1px]"
          >
            {savingLimit ? "Saving…" : "Save"}
          </button>
        </Card>

        <Card title="Change password">
          <input
            type="password"
            placeholder="Current password"
            value={pw.current}
            onChange={(e) => setPw({ ...pw, current: e.target.value })}
            data-testid="settings-current-pw"
            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none mb-2.5"
          />
          <input
            type="password"
            placeholder="New password"
            value={pw.next}
            onChange={(e) => setPw({ ...pw, next: e.target.value })}
            data-testid="settings-new-pw"
            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
          <button
            onClick={savePw}
            disabled={savingPw}
            data-testid="settings-save-pw"
            className="mt-3 w-full bg-slate-900 hover:bg-slate-800 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-all hover:-translate-y-[1px]"
          >
            {savingPw ? "Updating…" : "Update password"}
          </button>
        </Card>
      </div>

      <Card title="Company context (used by Gemini)" wide>
        <textarea
          value={context}
          onChange={(e) => setContext(e.target.value)}
          rows={18}
          data-testid="settings-context"
          className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm font-mono focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none"
        />
        <div className="mt-3 flex justify-end">
          <button
            onClick={saveContext}
            disabled={savingCtx}
            data-testid="settings-save-context"
            className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-all hover:-translate-y-[1px]"
          >
            {savingCtx ? "Saving…" : "Save context"}
          </button>
        </div>
      </Card>
    </div>
  );
}

function Card({ title, children, wide }) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-6 ${wide ? "" : ""}`}>
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 mb-4">{title}</div>
      {children}
    </div>
  );
}

function ProviderRow({ label, ok }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
      <div className="text-sm text-slate-800">{label}</div>
      {ok ? (
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
          <CheckCircle2 size={14} strokeWidth={1.8} /> Configured
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-700">
          <XCircle size={14} strokeWidth={1.8} /> Not configured
        </span>
      )}
    </div>
  );
}
