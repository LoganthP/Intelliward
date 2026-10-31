import { Component, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import { Button, ToastProvider } from "./components/ui";
import { AuthProvider, useAuth } from "./lib/auth";
import { LiveProvider } from "./lib/live";
import type { AccessRole } from "./lib/types";
import Alerts from "./pages/Alerts";
import Analytics from "./pages/Analytics";
import Audit from "./pages/Audit";
import LiveMonitoring from "./pages/LiveMonitoring";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import SettingsPage from "./pages/Settings";
import StaffPage from "./pages/Staff";
import Tasks from "./pages/Tasks";
import Visits from "./pages/Visits";
import WardsCameras from "./pages/WardsCameras";

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="grid min-h-[60vh] place-items-center p-6 text-center">
        <div className="glass-strong max-w-md p-8">
          <p className="font-display text-lg font-semibold">This page failed to load</p>
          <p className="mt-2 text-sm text-ink-soft">{this.state.error.message}</p>
          <Button className="mt-4" onClick={() => location.reload()}>Reload page</Button>
        </div>
      </div>
    );
  }
}

function Guard({ roles, children }: { roles?: AccessRole[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="grid min-h-full place-items-center"><div className="canvas-field" /><span className="h-8 w-8 animate-spin rounded-full border-[3px] border-teal border-r-transparent" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.access_role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function Routed() {
  const { user } = useAuth();
  const sup: AccessRole[] = ["admin", "supervisor"];
  return (
    <LiveProvider enabled={!!user}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Guard><Shell /></Guard>}>
          <Route index element={<ErrorBoundary><Overview /></ErrorBoundary>} />
          <Route path="live" element={<Guard roles={sup}><ErrorBoundary><LiveMonitoring /></ErrorBoundary></Guard>} />
          <Route path="tasks" element={<ErrorBoundary><Tasks /></ErrorBoundary>} />
          <Route path="visits" element={<ErrorBoundary><Visits /></ErrorBoundary>} />
          <Route path="alerts" element={<Guard roles={sup}><ErrorBoundary><Alerts /></ErrorBoundary></Guard>} />
          <Route path="staff" element={<Guard roles={sup}><ErrorBoundary><StaffPage /></ErrorBoundary></Guard>} />
          <Route path="wards" element={<Guard roles={sup}><ErrorBoundary><WardsCameras /></ErrorBoundary></Guard>} />
          <Route path="analytics" element={<Guard roles={sup}><ErrorBoundary><Analytics /></ErrorBoundary></Guard>} />
          <Route path="audit" element={<Guard roles={sup}><ErrorBoundary><Audit /></ErrorBoundary></Guard>} />
          <Route path="settings" element={<Guard roles={sup}><ErrorBoundary><SettingsPage /></ErrorBoundary></Guard>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </LiveProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routed />
      </ToastProvider>
    </AuthProvider>
  );
}
