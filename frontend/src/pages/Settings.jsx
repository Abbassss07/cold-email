import { useEffect, useRef, useState } from "react";
function EnvField({ k, label, type = "text", placeholder, help, value, onChange }) {
  return (
    <div>
      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">{label}</label>
      <input type={type} value={value} onChange={onChange} placeholder={placeholder}
        data-testid={`env-${k.toLowerCase()}`}
        className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none" />
      {help && <div className="text-xs text-slate-400 mt-1">{help}</div>}
    </div>
  );
}

import { toast } from "sonner";
import { CheckCircle2, XCircle, FileText, Upload, Trash2, Download } from "lucide-react";
import {
  changePassword,
  deletePdf,
  getSettings,
  pdfDownloadUrl,
  updateContext,
  updateDailyLimit,
  updateEnv,
  uploadPdf,
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

        <PdfCard pdf={data.pdf} onChanged={load} />

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

      <FirmProfileCard data={data} onSaved={load} />

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

function FirmProfileCard({ data, onSaved }) {
  const [form, setForm] = useState({
    COMPANY_NAME: data.company_name || "",
    FROM_NAME: data.from_name || "",
    FROM_EMAIL: data.from_email || "",
    DESIGNATION: data.designation || "",
    PHONE: data.phone || "",
    COMPANY_WEBSITE: data.company_website || "",
  });
  const [busy, setBusy] = useState(false);
  const f = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async () => {
    setBusy(true);
    try {
      await updateEnv(form);
      toast.success("Saved firm profile");
      onSaved?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const Field = ({ k, label, type = "text", placeholder, help }) => (
    <EnvField k={k} label={label} type={type} placeholder={placeholder} help={help} value={form[k]} onChange={f(k)} />
  );

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-6">
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 mb-4">Firm profile (used in email signatures)</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field k="COMPANY_NAME" label="Company name" placeholder="SDU Global Auditing" />
        <Field k="FROM_NAME" label="From name" placeholder="Mohammed Abbas" />
        <Field k="FROM_EMAIL" label="From email" placeholder="outreach@yourdomain.ae" help="Must be on a Resend-verified domain" />
        <Field k="DESIGNATION" label="Designation" placeholder="Business Advisory" />
        <Field k="PHONE" label="Phone" placeholder="+971 4 000 0000" />
        <Field k="COMPANY_WEBSITE" label="Website" placeholder="https://sduglobal.ae" />
      </div>
      <p className="mt-4 text-xs text-slate-500">Gemini and Resend API keys are managed securely in Vercel environment variables.</p>
      <div className="mt-5 flex justify-end">
        <button
          onClick={save}
          disabled={busy}
          data-testid="env-save-button"
          className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-all hover:-translate-y-[1px]"
        >
          {busy ? "Saving…" : "Save firm profile"}
        </button>
      </div>
    </div>
  );
}

function PdfCard({ pdf, onChanged }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);

  const handle = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Please choose a .pdf file");
      return;
    }
    setBusy(true);
    try {
      await uploadPdf(file);
      toast.success("Company profile PDF updated");
      onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm("Remove the attached company profile PDF?")) return;
    try {
      await deletePdf();
      toast.success("PDF removed");
      onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-6" data-testid="settings-pdf-card">
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 mb-4">Company profile PDF</div>
      {pdf?.present ? (
        <div className="flex items-start gap-3 mb-3 p-3 rounded-xl bg-slate-50 border border-slate-200">
          <div className="w-9 h-9 rounded-lg bg-[#2563EB] text-white flex items-center justify-center flex-shrink-0">
            <FileText size={18} strokeWidth={1.6} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-slate-900 truncate">Attached to every email</div>
            <div className="text-xs text-slate-500 tabular-nums">{Math.round((pdf.size || 0) / 1024)} KB</div>
          </div>
        </div>
      ) : (
        <div className="text-sm text-slate-500 mb-3 p-3 rounded-xl bg-amber-50 border border-amber-200" data-testid="pdf-empty-state">
          No PDF uploaded yet. Emails will be sent without an attachment.
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        data-testid="pdf-upload-input"
        onChange={(e) => handle(e.target.files?.[0])}
      />
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          data-testid="pdf-upload-button"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-[#2563EB] hover:bg-[#1D4ED8] text-white transition-all hover:-translate-y-[1px]"
        >
          <Upload size={14} strokeWidth={1.8} /> {busy ? "Uploading…" : pdf?.present ? "Replace" : "Upload"}
        </button>
        {pdf?.present && (
          <>
            <a
              href={pdfDownloadUrl}
              data-testid="pdf-download-link"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-all"
            >
              <Download size={14} strokeWidth={1.8} /> Preview
            </a>
            <button
              onClick={remove}
              data-testid="pdf-delete-button"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border border-red-200 bg-white text-red-700 hover:bg-red-50 transition-all"
            >
              <Trash2 size={14} strokeWidth={1.8} /> Remove
            </button>
          </>
        )}
      </div>
    </div>
  );
}
