import { useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { me } from "@/lib/api";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Logs from "@/pages/Logs";
import Settings from "@/pages/Settings";
import LeadProfile from "@/pages/LeadProfile";
import Layout from "@/components/Layout";

function Protected({ children, authed }) {
  if (authed === null) return <div className="p-10 text-slate-500 text-sm">Loading...</div>;
  if (!authed) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const [authed, setAuthed] = useState(null);

  const refresh = async () => {
    try {
      await me();
      setAuthed(true);
    } catch {
      setAuthed(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="app-root">
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              authed ? <Navigate to="/" replace /> : <Login onSuccess={() => setAuthed(true)} />
            }
          />
          <Route
            element={
              <Protected authed={authed}>
                <Layout onLogout={() => setAuthed(false)} />
              </Protected>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/leads/:id" element={<LeadProfile />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" />
    </div>
  );
}
