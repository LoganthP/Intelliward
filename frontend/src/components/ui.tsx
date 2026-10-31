import { AnimatePresence, motion } from "framer-motion";
import clsx from "clsx";
import { X, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { pretty } from "../lib/format";

export function Panel({ className, children, strong, as: As = "section" }: { className?: string; children: ReactNode; strong?: boolean; as?: "section" | "div" | "article" }) {
  return <As className={clsx(strong ? "glass-strong" : "glass", className)}>{children}</As>;
}

export function PanelHead({ title, hint, action }: { title: ReactNode; hint?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pt-4">
      <div className="min-w-0">
        <h2 className="h-card">{title}</h2>
        {hint && <p className="mt-0.5 text-[13px] text-ink-faint">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "soft" | "ghost" | "danger"; size?: "sm" | "md"; icon?: ReactNode; busy?: boolean };

export function Button({ variant = "primary", size = "md", icon, busy, className, children, disabled, ...rest }: BtnProps) {
  const base = "inline-flex select-none items-center justify-center gap-2 rounded-xl font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const sizes = { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4 text-sm" };
  const variants = {
    primary: "bg-teal text-white shadow-clay hover:bg-teal-deep",
    soft: "bg-white/80 text-ink border border-ink/10 hover:bg-white shadow-[0_6px_14px_-10px_rgba(15,46,68,0.4)]",
    ghost: "text-ink-soft hover:bg-white/70 hover:text-ink",
    danger: "bg-coral text-white shadow-[0_10px_18px_-10px_rgba(229,72,77,0.6)] hover:bg-[#cf3a3f]",
  };
  return (
    <motion.button
      whileTap={disabled || busy ? undefined : { scale: 0.95, y: 1 }}
      transition={{ type: "spring", stiffness: 600, damping: 22 }}
      className={clsx(base, sizes[size], variants[variant], className)}
      disabled={disabled || busy}
      {...(rest as any)}
    >
      {busy ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" /> : icon}
      {children}
    </motion.button>
  );
}

const TONES = {
  teal: "bg-teal-tint text-teal-deep", mint: "bg-mint-tint text-[#137a62]", sky: "bg-sky-tint text-[#1f6bb5]",
  coral: "bg-coral-tint text-[#b42a2f]", amber: "bg-amber-tint text-[#9a5c06]", slate: "bg-ink/[0.06] text-ink-soft",
};
export type Tone = keyof typeof TONES;

export function Badge({ tone = "slate", children, dot, className }: { tone?: Tone; children: ReactNode; dot?: boolean; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold", TONES[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export const statusTone = (s: string): Tone =>
  ({ verified: "mint", online: "mint", active: "teal", resolved: "mint", in_progress: "sky", acknowledged: "sky",
     review_required: "amber", starting: "amber", pending: "slate", exited: "slate", stopped: "slate", dismissed: "slate",
     overdue: "coral", rejected: "coral", offline: "coral", open: "coral" } as Record<string, Tone>)[s] ?? "slate";

export const severityTone = (s: string): Tone => ({ low: "sky", medium: "amber", high: "coral", critical: "coral" } as Record<string, Tone>)[s] ?? "slate";

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={statusTone(status)} dot>{pretty(status)}</Badge>;
}

export function Progress({ value, tone = "teal" }: { value: number; tone?: "teal" | "mint" | "amber" }) {
  const color = { teal: "bg-teal", mint: "bg-mint", amber: "bg-amber" }[tone];
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-ink/[0.07]">
      <motion.div className={clsx("h-full rounded-full", color)} initial={false}
        animate={{ width: `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%` }} transition={{ type: "spring", stiffness: 120, damping: 20 }} />
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-xl bg-ink/[0.06]", className)} />;
}

export function Empty({ icon, title, body, action }: { icon?: ReactNode; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      {icon && <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-teal-tint text-teal">{icon}</div>}
      <p className="font-display text-[15px] font-semibold text-ink">{title}</p>
      {body && <p className="mt-1 max-w-sm text-sm text-ink-faint">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-coral/20 bg-coral-tint/70 px-4 py-3 text-sm text-[#9b2328]">
      <AlertTriangle size={16} className="shrink-0" />
      <span className="flex-1">{message}</span>
      {onRetry && <Button size="sm" variant="soft" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center p-3 sm:items-center sm:p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-[#0f2e44]/20 backdrop-blur-sm" onClick={onClose} />
          <motion.div role="dialog" aria-modal="true" aria-label={title}
            className={clsx("glass-strong relative max-h-[92vh] w-full overflow-y-auto", wide ? "max-w-3xl" : "max-w-lg")}
            initial={{ y: 24, scale: 0.97, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} exit={{ y: 16, scale: 0.98, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}>
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-ink/5 bg-white/70 px-5 py-3.5 backdrop-blur-xl">
              <h3 className="font-display text-base font-semibold">{title}</h3>
              <button onClick={onClose} className="rounded-lg p-1.5 text-ink-faint hover:bg-ink/5 hover:text-ink" aria-label="Close"><X size={18} /></button>
            </div>
            <div className="p-5">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ toasts */
type Toast = { id: number; tone: "ok" | "warn" | "info"; title: string; body?: string };
const ToastCtx = createContext<(t: Omit<Toast, "id">) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-3), { ...t, id }]);
    window.setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), t.tone === "warn" ? 7000 : 4000);
  }, []);
  const icon = { ok: <CheckCircle2 size={18} className="text-mint" />, warn: <AlertTriangle size={18} className="text-coral" />, info: <Info size={18} className="text-sky" /> };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div key={t.id} layout initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }}
              transition={{ type: "spring", stiffness: 420, damping: 32 }}
              className="glass-strong pointer-events-auto flex gap-3 px-4 py-3">
              <div className="mt-0.5">{icon[t.tone]}</div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{t.title}</p>
                {t.body && <p className="mt-0.5 text-[13px] text-ink-soft">{t.body}</p>}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-faint">{hint}</span>}
    </label>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="flex items-center gap-3 text-sm text-ink">
      <span className={clsx("relative h-6 w-11 rounded-full transition-colors", checked ? "bg-teal" : "bg-ink/15")}>
        <motion.span layout transition={{ type: "spring", stiffness: 600, damping: 30 }}
          className={clsx("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow", checked ? "right-0.5" : "left-0.5")} />
      </span>
      {label}
    </button>
  );
}

export function Table({ head, children, empty }: { head: string[]; children: ReactNode; empty?: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="text-[12.5px] text-ink-faint">
            {head.map((h) => <th key={h} className="whitespace-nowrap px-5 py-2.5 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink/[0.06]">{children}</tbody>
      </table>
      {empty}
    </div>
  );
}
