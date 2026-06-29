const MAP = {
  pending: "bg-slate-100 text-slate-700 border-slate-200",
  generated: "bg-blue-50 text-[#2563EB] border-blue-100",
  sending: "bg-amber-50 text-amber-700 border-amber-100",
  sent: "bg-emerald-50 text-emerald-700 border-emerald-100",
  failed: "bg-red-50 text-red-700 border-red-100",
};
const LABEL = {
  pending: "Pending",
  generated: "Ready",
  sending: "Sending",
  sent: "Sent",
  failed: "Failed",
};

export default function StatusBadge({ status }) {
  const cls = MAP[status] || MAP.pending;
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${cls}`}>
      {LABEL[status] || status}
    </span>
  );
}
