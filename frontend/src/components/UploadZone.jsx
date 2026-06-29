import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { uploadCsv } from "@/lib/api";

export default function UploadZone({ onImported }) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  const handle = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      toast.error("Please upload a .csv file");
      return;
    }
    setBusy(true);
    try {
      const { data } = await uploadCsv(file);
      const skipped = data.skipped?.length || 0;
      toast.success(`Imported ${data.imported} companies${skipped ? ` (${skipped} skipped)` : ""}`);
      onImported?.(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid="upload-zone"
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files?.[0];
        handle(f);
      }}
      onClick={() => inputRef.current?.click()}
      className={`upload-zone ${dragging ? "dragging" : ""} w-full border-2 border-dashed border-slate-300 rounded-2xl p-10 text-center cursor-pointer group flex flex-col items-center justify-center bg-white hover:bg-slate-50 hover:border-[#2563EB]`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        data-testid="upload-input"
        onChange={(e) => handle(e.target.files?.[0])}
      />
      <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#2563EB] flex items-center justify-center mb-4 transition-transform group-hover:scale-105">
        <UploadCloud size={22} strokeWidth={1.6} />
      </div>
      <div className="text-base font-semibold text-slate-900">
        {busy ? "Uploading..." : "Drop your CSV here or click to browse"}
      </div>
      <div className="mt-1.5 text-sm text-slate-500">
        Required columns: <code className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">company_name</code>,{" "}
        <code className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">contact_email</code>
        &nbsp;•&nbsp;Optional: <code className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">website</code>,{" "}
        <code className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">notes</code>
      </div>
    </div>
  );
}
