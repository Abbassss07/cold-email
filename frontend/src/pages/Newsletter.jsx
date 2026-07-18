import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Send, Paperclip, X } from "lucide-react";
import { getContactLists, getSettings, sendNewsletter } from "@/lib/api";

const fileToBase64 = (file) => new Promise((resolve, reject) => {
  const r = new FileReader();
  r.onerror = reject;
  r.onload = () => resolve(r.result.split(",")[1]);
  r.readAsDataURL(file);
});

export default function Newsletter() {
  const [lists, setLists] = useState([]);
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState({
    list_id: "", campaign_name: "", subject: "",
    body_html: "", from_email: "", from_name: "",
  });
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [testTo, setTestTo] = useState("");
  const fileRef = useRef(null);

  useEffect(() => {
    (async () => {
      const [{ data: ls }, { data: s }] = await Promise.all([getContactLists(), getSettings()]);
      setLists(ls);
      setSettings(s);
      setForm((f) => ({
        ...f,
        from_email: s.newsletter_from_email || s.from_email || "",
        from_name: s.newsletter_from_name || s.from_name || "",
      }));
      setTestTo(s.newsletter_from_email || s.from_email || "");
    })();
  }, []);

  const setF = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const attach = async (fileList) => {
    const list = Array.from(fileList || []);
    const encoded = await Promise.all(list.map(async (f) => ({
      filename: f.name,
      content_b64: await fileToBase64(f),
      size: f.size,
    })));
    setFiles([...files, ...encoded]);
  };

  const removeFile = (i) => setFiles(files.filter((_, idx) => idx !== i));

  const validate = () => {
    if (!form.list_id) { toast.error("Choose a contact list"); return false; }
    if (!form.subject) { toast.error("Subject required"); return false; }
    if (!form.body_html) { toast.error("Body required"); return false; }
    if (!form.from_email) { toast.error("From email required"); return false; }
    return true;
  };

  const doSend = async ({ test_only }) => {
    if (!validate()) return;
    setBusy(true);
    try {
      const payload = {
        ...form,
        campaign_name: form.campaign_name || `Newsletter ${new Date().toLocaleDateString()}`,
        attachments: files.map((f) => ({ filename: f.filename, content_b64: f.content_b64 })),
        test_only,
        test_to: test_only ? testTo : undefined,
        body_text: form.body_html.replace(/<[^>]+>/g, "").trim(),
      };
      const { data } = await sendNewsletter(payload);
      if (test_only) {
        toast.success(`Test sent to ${testTo}`);
      } else {
        toast.success(`Newsletter sent — ${data.sent} succeeded, ${data.failed} failed`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Send failed");
    } finally { setBusy(false); }
  };

  const selectedList = lists.find((l) => l.id === form.list_id);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Newsletter</h1>
        <p className="text-sm text-slate-500 mt-1.5">Send a newsletter to a saved contact list. No AI — clean templated sends.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-6 space-y-4">
          <Row label="Contact list">
            <select value={form.list_id} onChange={setF("list_id")} data-testid="nl-list" className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-white outline-none focus:border-[#2563EB]">
              <option value="">— choose —</option>
              {lists.map((l) => <option key={l.id} value={l.id}>{l.name} ({l.count})</option>)}
            </select>
          </Row>

          <Row label="Campaign name">
            <input value={form.campaign_name} onChange={setF("campaign_name")} placeholder="e.g. July UAE VAT update" data-testid="nl-campaign" className={inputCls} />
          </Row>

          <div className="grid grid-cols-2 gap-3">
            <Row label="From name">
              <input value={form.from_name} onChange={setF("from_name")} data-testid="nl-from-name" className={inputCls} />
            </Row>
            <Row label="From email">
              <input value={form.from_email} onChange={setF("from_email")} data-testid="nl-from-email" className={inputCls} />
            </Row>
          </div>

          <Row label="Subject">
            <input value={form.subject} onChange={setF("subject")} placeholder="Use {{name}} or {{company}} for personalization" data-testid="nl-subject" className={inputCls} />
          </Row>

          <Row label="Body (HTML)">
            <textarea rows={12} value={form.body_html} onChange={setF("body_html")} placeholder="<p>Hello {{name}},</p><p>...</p>" data-testid="nl-body" className={`${inputCls} font-mono text-xs`} />
          </Row>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Attachments</label>
            <input ref={fileRef} type="file" multiple className="hidden" data-testid="nl-file-input" onChange={(e) => attach(e.target.files)} accept=".pdf,.docx,.xlsx,.doc,.xls,.txt,.png,.jpg,.jpeg" />
            <button onClick={() => fileRef.current?.click()} data-testid="nl-attach-btn" className="inline-flex items-center gap-2 border border-slate-200 rounded-xl px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              <Paperclip size={14} /> Add attachment
            </button>
            {files.length > 0 && (
              <ul className="mt-3 space-y-1">
                {files.map((f, i) => (
                  <li key={i} className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm">
                    <span className="truncate">{f.filename} <span className="text-slate-400 text-xs">({Math.round(f.size / 1024)} KB)</span></span>
                    <button onClick={() => removeFile(i)} className="text-slate-400 hover:text-red-600"><X size={14} /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 mb-3">Summary</div>
            <div className="text-sm space-y-1.5 text-slate-700">
              <div>List: <span className="font-medium">{selectedList?.name || "—"}</span></div>
              <div>Recipients: <span className="font-medium tabular-nums">{selectedList?.count || 0}</span></div>
              <div>Attachments: <span className="font-medium tabular-nums">{files.length}</span></div>
              <div>From: <span className="font-mono text-xs">{form.from_name} &lt;{form.from_email}&gt;</span></div>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 mb-3">Send test</div>
            <input value={testTo} onChange={(e) => setTestTo(e.target.value)} data-testid="nl-test-to" className={inputCls + " mb-2"} />
            <button onClick={() => doSend({ test_only: true })} disabled={busy} data-testid="nl-test-send" className="w-full inline-flex items-center justify-center gap-2 border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-medium hover:bg-slate-50">
              <Send size={14} /> Send test
            </button>
          </div>

          <button onClick={() => { if (window.confirm(`Send to ${selectedList?.count || 0} contacts?`)) doSend({ test_only: false }); }} disabled={busy || !selectedList} data-testid="nl-send-all" className="w-full bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl px-4 py-3 text-sm font-semibold transition-all hover:-translate-y-[1px] hover:shadow-md hover:shadow-blue-500/20 disabled:opacity-50">
            {busy ? "Sending…" : `Send Newsletter${selectedList ? ` (${selectedList.count})` : ""}`}
          </button>
        </div>
      </div>
    </div>
  );
}

const inputCls = "w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-white outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20";
function Row({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">{label}</label>
      {children}
    </div>
  );
}
