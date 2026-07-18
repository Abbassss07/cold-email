import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Users, Upload, Pencil, Trash2, RefreshCw, Search } from "lucide-react";
import {
  deleteContactList, getContactLists, renameContactList,
  replaceContactList, uploadContactList,
} from "@/lib/api";

export default function ContactLists() {
  const [lists, setLists] = useState([]);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [q, setQ] = useState("");
  const inputRef = useRef(null);
  const replaceRefs = useRef({});

  const load = async () => {
    const { data } = await getContactLists();
    setLists(data);
  };
  useEffect(() => { load(); }, []);

  const handleFile = async (file) => {
    if (!file) return;
    if (!name.trim()) { toast.error("Enter a list name first"); return; }
    setBusy(true);
    try {
      const { data } = await uploadContactList(file, name.trim());
      toast.success(`Saved ${data.count} contacts${data.skipped ? ` (${data.skipped} skipped)` : ""}`);
      setName("");
      inputRef.current.value = "";
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Upload failed"); }
    finally { setBusy(false); }
  };

  const doRename = async (id, current) => {
    const next = window.prompt("Rename list:", current);
    if (!next || next === current) return;
    await renameContactList(id, next);
    toast.success("Renamed");
    load();
  };

  const doReplace = async (id, file) => {
    if (!file) return;
    try {
      const { data } = await replaceContactList(id, file);
      toast.success(`Replaced with ${data.count} contacts`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Replace failed"); }
  };

  const doDelete = async (id, listName) => {
    if (!window.confirm(`Delete list "${listName}"?`)) return;
    await deleteContactList(id);
    toast.success("Deleted");
    load();
  };

  const filtered = lists.filter((l) =>
    !q || l.name.toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Contact Lists</h1>
        <p className="text-sm text-slate-500 mt-1.5">Reusable audiences for newsletters and campaigns.</p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-6">
        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 mb-4">Upload new list</div>
        <div className="flex flex-wrap gap-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="List name (e.g. UAE Prospects – July)"
            data-testid="new-list-name"
            className="flex-1 min-w-[220px] border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20"
          />
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            className="hidden"
            data-testid="new-list-file"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <button
            onClick={() => inputRef.current?.click()}
            disabled={busy}
            data-testid="new-list-upload-btn"
            className="inline-flex items-center gap-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-all hover:-translate-y-[1px]"
          >
            <Upload size={16} strokeWidth={1.6} /> {busy ? "Uploading…" : "Upload CSV"}
          </button>
        </div>
        <div className="text-xs text-slate-400 mt-2">
          CSV columns: <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-[11px]">contact_email</code> (required),
          <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-[11px] ml-1">contact_name</code>,
          <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-[11px] ml-1">company_name</code>,
          <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-[11px] ml-1">industry</code>.
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search size={16} strokeWidth={1.6} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search lists…"
            data-testid="contact-list-search"
            className="w-full bg-white border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-14 text-center" data-testid="contact-lists-empty">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-slate-100 text-slate-500 flex items-center justify-center mb-4">
            <Users size={22} strokeWidth={1.6} />
          </div>
          <div className="text-base font-semibold text-slate-900">No contact lists yet</div>
          <div className="text-sm text-slate-500 mt-1">Upload a CSV to create your first list.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((l) => (
            <div key={l.id} data-testid={`list-${l.id}`} className="bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-5 hover:-translate-y-[1px] hover:shadow-md transition-all">
              <div className="flex items-start justify-between mb-3">
                <div className="min-w-0">
                  <div className="text-base font-semibold text-slate-900 truncate">{l.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{l.count} contacts · updated {new Date(l.updated_at).toLocaleDateString()}</div>
                </div>
              </div>
              <input
                ref={(el) => (replaceRefs.current[l.id] = el)}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => doReplace(l.id, e.target.files?.[0])}
              />
              <div className="flex gap-1 mt-3">
                <button onClick={() => doRename(l.id, l.name)} data-testid={`rename-${l.id}`} className="flex-1 inline-flex items-center justify-center gap-1.5 border border-slate-200 rounded-xl px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50">
                  <Pencil size={13} /> Rename
                </button>
                <button onClick={() => replaceRefs.current[l.id]?.click()} data-testid={`replace-${l.id}`} className="flex-1 inline-flex items-center justify-center gap-1.5 border border-slate-200 rounded-xl px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50">
                  <RefreshCw size={13} /> Replace
                </button>
                <button onClick={() => doDelete(l.id, l.name)} data-testid={`delete-${l.id}`} className="inline-flex items-center justify-center border border-red-200 text-red-700 rounded-xl px-3 py-2 hover:bg-red-50">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
