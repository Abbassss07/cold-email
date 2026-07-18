import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, Mail, Newspaper, History, Users, Settings as SettingsIcon, LogOut, ShieldCheck, ScrollText } from "lucide-react";
import { logout } from "@/lib/api";
import { toast } from "sonner";

export default function Layout({ onLogout }) {
  const navigate = useNavigate();
  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      // ignore — we still want to redirect
    }
    onLogout?.();
    toast.success("Signed out");
    navigate("/login");
  };

  const navItem = ({ isActive }) =>
    `flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
      isActive ? "bg-slate-900 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
    }`;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 bg-white/80 backdrop-blur border-b border-slate-200">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#2563EB] text-white flex items-center justify-center">
              <ShieldCheck size={18} strokeWidth={1.8} />
            </div>
            <div>
              <div className="text-sm font-bold tracking-tight text-slate-900">SDU Connect</div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400 -mt-0.5">Outreach · Newsletter · CRM</div>
            </div>
          </div>
          <nav className="hidden lg:flex items-center gap-1">
            <NavLink to="/" end className={navItem} data-testid="nav-dashboard"><LayoutDashboard size={15} strokeWidth={1.6} /> Dashboard</NavLink>
            <NavLink to="/outreach" className={navItem} data-testid="nav-outreach"><Mail size={15} strokeWidth={1.6} /> Cold Outreach</NavLink>
            <NavLink to="/newsletter" className={navItem} data-testid="nav-newsletter"><Newspaper size={15} strokeWidth={1.6} /> Newsletter</NavLink>
            <NavLink to="/contacts" className={navItem} data-testid="nav-contacts"><Users size={15} strokeWidth={1.6} /> Contacts</NavLink>
            <NavLink to="/campaigns" className={navItem} data-testid="nav-campaigns"><History size={15} strokeWidth={1.6} /> Campaigns</NavLink>
            <NavLink to="/logs" className={navItem} data-testid="nav-logs"><ScrollText size={15} strokeWidth={1.6} /> Logs</NavLink>
            <NavLink to="/settings" className={navItem} data-testid="nav-settings"><SettingsIcon size={15} strokeWidth={1.6} /> Settings</NavLink>
          </nav>
          <button
            onClick={handleLogout}
            data-testid="logout-button"
            className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 rounded-xl px-3 py-2 hover:bg-slate-100 transition-all"
          >
            <LogOut size={16} strokeWidth={1.6} /> <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
        <nav className="lg:hidden flex items-center gap-1 px-6 pb-3 overflow-x-auto">
          <NavLink to="/" end className={navItem}>Dashboard</NavLink>
          <NavLink to="/outreach" className={navItem}>Outreach</NavLink>
          <NavLink to="/newsletter" className={navItem}>Newsletter</NavLink>
          <NavLink to="/contacts" className={navItem}>Contacts</NavLink>
          <NavLink to="/campaigns" className={navItem}>Campaigns</NavLink>
          <NavLink to="/settings" className={navItem}>Settings</NavLink>
        </nav>
      </header>

      <main className="flex-1 max-w-[1280px] w-full mx-auto px-6 lg:px-10 py-8 fade-in">
        <Outlet />
      </main>
    </div>
  );
}
