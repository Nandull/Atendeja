/**
 * Componentes de interface no estilo shadcn/ui (Tailwind puro, sem dependências).
 * Mantêm a mesma API dos componentes do shadcn para facilitar trocar depois.
 */
import { Loader2, X } from "lucide-react";
import {
  forwardRef,
  useEffect,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import { cn } from "@/lib/cn";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
        "disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "h-8 px-3 text-sm" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-brand-700 text-white hover:bg-brand-800",
        variant === "secondary" &&
          "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50",
        variant === "ghost" && "text-slate-700 hover:bg-slate-100",
        variant === "danger" && "bg-red-600 text-white hover:bg-red-700",
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

// Largura padrão 100%, a menos que o componente receba outra largura (w-32 etc.).
const width = (className?: string) => (/(^|\s)w-/.test(className ?? "") ? undefined : "w-full");

const fieldBase =
  "rounded-lg border border-slate-300 bg-white px-3 text-sm shadow-xs " +
  "placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 " +
  "focus:ring-brand-100 disabled:bg-slate-100";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(fieldBase, width(className), "h-10", className)} {...props} />
  ),
);
Input.displayName = "Input";

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(fieldBase, width(className), "min-h-20 py-2", className)} {...props} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(fieldBase, width(className), "h-10", className)} {...props} />;
}

/** Rótulo + campo + dica/erro, com acessibilidade ligada automaticamente. */
export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: (id: string) => ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children(id)}
      {error ? (
        <p className="text-xs text-red-600">{error}</p>
      ) : hint ? (
        <p className="text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}

export function Checkbox({
  label,
  checked,
  onChange,
  description,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  description?: string;
}) {
  const id = useId();
  return (
    <div className="flex items-start gap-2">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 size-4 rounded border-slate-300 accent-brand-700"
      />
      <label htmlFor={id} className="text-sm">
        <span className="font-medium text-slate-800">{label}</span>
        {description && <span className="block text-slate-500">{description}</span>}
      </label>
    </div>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("rounded-xl border border-slate-200 bg-white shadow-xs", className)}>
      {children}
    </div>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "success" | "warning";
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        tone === "neutral" && "bg-slate-100 text-slate-700",
        tone === "success" && "bg-emerald-50 text-emerald-700",
        tone === "warning" && "bg-amber-50 text-amber-800",
      )}
    >
      {children}
    </span>
  );
}

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {children}
    </div>
  );
}

export function Spinner({ label = "Carregando..." }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-slate-500" role="status">
      <Loader2 className="size-4 animate-spin" aria-hidden /> {label}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <p className="font-medium text-slate-800">{title}</p>
      {description && <p className="max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

/** Painel lateral para formulários de criar/editar. Fecha com Esc. */
export function Sheet({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative flex h-full w-full max-w-md flex-col bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
            aria-label="Fechar"
          >
            <X className="size-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
      </div>
    </div>
  );
}
