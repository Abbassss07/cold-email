import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { regenerate, updateEmail } from "@/lib/api";
import { RefreshCw, Save } from "lucide-react";

export default function EmailEditDialog({ email, open, onClose, onChanged }) {
  const [subject, setSubject] = useState("");
  const [intro, setIntro] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [regenBusy, setRegenBusy] = useState(false);

  useEffect(() => {
    if (email) {
      setSubject(email.subject || "");
      setIntro(email.intro || "");
      setBody(email.body || "");
    }
  }, [email]);

  if (!email) return null;

  const introWords = intro.trim() ? intro.trim().split(/\s+/).length : 0;
  const overLimit = introWords > 80;

  const save = async () => {
    setBusy(true);
    try {
      await updateEmail(email.id, { subject, intro, body });
      toast.success("Saved");
      onChanged?.();
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const doRegenerate = async () => {
    setRegenBusy(true);
    try {
      const { data } = await regenerate(email.id);
      setSubject(data.subject || "");
      setIntro(data.intro || "");
      setBody(data.body || "");
      toast.success("Regenerated");
      onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Regeneration failed");
    } finally {
      setRegenBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => (!o ? onClose() : null)}>
      <DialogContent className="max-w-2xl rounded-2xl" data-testid="email-edit-dialog">
        <DialogHeader>
          <DialogTitle className="tracking-tight">{email.company_name}</DialogTitle>
          <div className="text-xs text-slate-500 font-mono">{email.contact_email}</div>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Subject</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              data-testid="edit-subject-input"
              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none"
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Personalized intro <span className="text-slate-400 normal-case font-normal">(AI-generated, max 80 words)</span>
              </label>
              <span className={`text-xs tabular-nums ${overLimit ? "text-red-600 font-semibold" : "text-slate-400"}`}>
                {introWords}/80 words
              </span>
            </div>
            <textarea
              value={intro}
              onChange={(e) => setIntro(e.target.value)}
              data-testid="edit-intro-input"
              rows={5}
              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none"
            />
          </div>

          <div className="rounded-xl bg-slate-50 border border-slate-200 px-4 py-3 text-xs text-slate-600">
            <div className="font-semibold text-slate-700 mb-1">Fixed by template (not AI-generated):</div>
            Company services description • Call to action • Signature • Attached company profile PDF
          </div>
        </div>

        <DialogFooter className="mt-4 gap-2">
          <button
            onClick={doRegenerate}
            disabled={regenBusy}
            data-testid="edit-regenerate-button"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-all"
          >
            <RefreshCw size={16} strokeWidth={1.6} className={regenBusy ? "animate-spin" : ""} />
            {regenBusy ? "Regenerating..." : "Regenerate with AI"}
          </button>
          <button
            onClick={save}
            disabled={busy}
            data-testid="edit-save-button"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium bg-[#2563EB] hover:bg-[#1D4ED8] text-white transition-all hover:-translate-y-[1px]"
          >
            <Save size={16} strokeWidth={1.6} />
            {busy ? "Saving..." : "Save"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
