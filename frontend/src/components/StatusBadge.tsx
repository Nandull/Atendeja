import { STATUS_LABEL, type AppointmentStatus } from "@/api/types";
import { cn } from "@/lib/cn";

const TONE: Record<AppointmentStatus, string> = {
  scheduled: "bg-sky-50 text-sky-700",
  confirmed: "bg-emerald-50 text-emerald-700",
  completed: "bg-slate-100 text-slate-700",
  canceled: "bg-slate-100 text-slate-500 line-through",
  no_show: "bg-red-50 text-red-700",
};

export function StatusBadge({ status }: { status: AppointmentStatus }) {
  return (
    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium", TONE[status])}>
      {STATUS_LABEL[status]}
    </span>
  );
}
