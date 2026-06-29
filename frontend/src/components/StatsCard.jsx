export default function StatsCard({ label, value, accent = "default", testId }) {
  const palettes = {
    default: "text-slate-900",
    blue: "text-[#2563EB]",
    green: "text-emerald-700",
    red: "text-red-700",
    amber: "text-amber-700",
  };
  return (
    <div
      data-testid={testId}
      className="bg-white rounded-2xl border border-slate-200 shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-6 transition-all hover:-translate-y-[1px] hover:shadow-md"
    >
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className={`mt-3 text-4xl font-bold tracking-tighter tabular-nums ${palettes[accent] || palettes.default}`}>
        {value}
      </div>
    </div>
  );
}
