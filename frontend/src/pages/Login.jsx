import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { login } from "@/lib/api";

const BG = "https://images.pexels.com/photos/28506788/pexels-photo-28506788.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=900&w=1200";

export default function Login({ onSuccess }) {
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!password) return;
    setLoading(true);
    try {
      await login(password);
      toast.success("Welcome back");
      onSuccess();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-white">
      <div className="hidden lg:block relative overflow-hidden">
        <img src={BG} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-tr from-slate-900/40 via-slate-900/10 to-transparent" />
        <div className="relative h-full flex flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-2 text-base font-semibold tracking-tight">
            <ShieldCheck size={22} strokeWidth={1.5} />
            SDU Global Auditing
          </div>
          <div>
            <div className="text-3xl font-bold tracking-tight max-w-md leading-tight">
              Precise outreach. Built for auditors.
            </div>
            <div className="mt-3 text-sm text-white/80 max-w-md">
              Compose, review and send personalized cold emails in minutes — never crowded, never noisy.
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8 fade-in">
        <form onSubmit={submit} className="w-full max-w-sm" data-testid="login-form">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#2563EB] mb-3">Admin</div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">Sign in</h1>
          <p className="text-sm text-slate-500 mb-8">
            Enter your administrator password to access the outreach console.
          </p>

          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
            placeholder="••••••••"
            data-testid="login-password-input"
            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-900 focus:border-[#2563EB] focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
          />

          <button
            type="submit"
            disabled={loading}
            data-testid="login-submit-button"
            className="mt-6 w-full bg-[#2563EB] hover:bg-[#1D4ED8] disabled:opacity-60 text-white rounded-xl px-5 py-3 font-medium transition-all duration-200 hover:-translate-y-[1px] hover:shadow-md hover:shadow-blue-500/20 flex items-center justify-center gap-2"
          >
            {loading ? <span className="spinner" /> : null}
            {loading ? "Signing in..." : "Sign in"}
          </button>

          <div className="mt-10 text-xs text-slate-400">
            Protected session • HTTP-only cookie
          </div>
        </form>
      </div>
    </div>
  );
}
