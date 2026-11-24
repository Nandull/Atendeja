import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ClientHistory as History } from "@/api/types";
import { StatusBadge } from "@/components/StatusBadge";
import { Spinner } from "@/components/ui";
import { formatDate, formatMoney, formatTime } from "@/lib/format";

export function ClientHistory({ clientId }: { clientId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["client-history", clientId],
    queryFn: () => api<History>(`/clients/${clientId}/history`, { query: { limit: 20 } }),
  });
  if (isLoading || !data) return <Spinner />;
  const s = data.stats;
  const daysSince = s.last_visit
    ? Math.floor((Date.now() - new Date(s.last_visit).getTime()) / 86_400_000)
    : null;

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-3 gap-2 text-center">
        {[
          { label: "Atendimentos", value: s.completed },
          { label: "Faltas", value: s.no_show },
          { label: "Gasto total", value: formatMoney(s.total_spent_cents) },
          { label: "Última visita", value: daysSince === null ? "—" : daysSince === 0 ? "hoje" : `há ${daysSince} dias` },
          { label: "Frequência", value: s.avg_days_between_visits ? `a cada ${Math.round(s.avg_days_between_visits)} dias` : "—" },
          { label: "Agendados", value: s.upcoming },
        ].map((x) => (
          <div key={x.label} className="rounded-lg bg-slate-50 px-2 py-2">
            <dt className="text-xs text-slate-500">{x.label}</dt>
            <dd className="text-sm font-semibold">{x.value}</dd>
          </div>
        ))}
      </dl>
      {data.appointments.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum atendimento ainda.</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {data.appointments.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 py-2">
              <div>
                <p className="font-medium">{a.service.name}</p>
                <p className="text-xs text-slate-500">
                  {formatDate(a.starts_at)} {formatTime(a.starts_at)} · {a.professional.name}
                </p>
              </div>
              <StatusBadge status={a.status} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
