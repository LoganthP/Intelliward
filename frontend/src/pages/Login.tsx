import { motion } from "framer-motion";
import { Activity, LockKeyhole } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { Button, ErrorNote, Field } from "../components/ui";
import { useAuth } from "../lib/auth";

const DEMO = [
  { u: "admin", p: "admin123", label: "Administrator" },
  { u: "supervisor", p: "super123", label: "Supervisor" },
  { u: "nurse1", p: "staff123", label: "Staff (Asha Rao)" },
];

export default function Login() {
  const { user, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (user) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try { await login(username.trim().toLowerCase(), password); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-full place-items-center p-4">
      <div className="canvas-field" />
      <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", stiffness: 140, damping: 20 }}
        className="glass-strong grid w-full max-w-4xl overflow-hidden md:grid-cols-[1.05fr_1fr]">
        <div className="relative hidden flex-col justify-between bg-gradient-to-br from-teal to-[#0d5f8a] p-8 text-white md:flex">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-white/15"><Activity size={22} /></div>
            <span className="font-display text-xl font-semibold tracking-[-0.02em]">IntelliWard</span>
          </div>
          <div>
            <p className="font-display text-[2rem] font-semibold leading-[1.15] tracking-[-0.03em]">Who was in the ward, for how long, and was the work done.</p>
            <p className="mt-4 max-w-sm text-[15px] leading-relaxed text-white/80">
              Verified staff identity, ward visits, evidence-based task checks and an audit trail that shows any tampering.
            </p>
          </div>
          <svg viewBox="0 0 400 60" className="w-full opacity-80" aria-hidden>
            <path d="M0 30 H120 L132 22 L142 30 L150 36 L160 6 L170 50 L180 30 L196 26 L206 30 H400" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-4 p-7 sm:p-9">
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-[-0.02em]">Sign in</h1>
            <p className="mt-1 text-sm text-ink-soft">Use your hospital account.</p>
          </div>
          <Field label="Username"><input className="field" autoFocus autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></Field>
          <Field label="Password"><input className="field" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
          {error && <ErrorNote message={error} />}
          <Button type="submit" busy={busy} icon={<LockKeyhole size={16} />} className="mt-1 h-11">Sign in</Button>
          <div className="mt-2 rounded-2xl bg-teal-tint/60 p-3">
            <p className="text-[13px] font-medium text-teal-deep">Demo accounts</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {DEMO.map((d) => (
                <button type="button" key={d.u} onClick={() => { setUsername(d.u); setPassword(d.p); }}
                  className="rounded-full border border-teal/20 bg-white/80 px-3 py-1 text-[13px] font-medium text-ink hover:border-teal/50">
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
