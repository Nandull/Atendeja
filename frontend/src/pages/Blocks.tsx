import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { useProfessionals } from "@/api/hooks";
import type { TimeBlock } from "@/api/types";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Sheet,
  Spinner,
} from "@/components/ui";
import { formatDateTime } from "@/lib/format";

const DAYS_AHEAD = 120;

export function BlocksPage() {
  const { session, can } = useAuth();
  const qc = useQueryClient();
  const pros = useProfessionals();
  const [filter, setFilter] = useState("");
  const [creating, setCreating] = useState(false);

  const range = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const end = new Date(start.getTime() + DAYS_AHEAD * 86_400_000);
    return { start: start.toISOString(), end: end.toISOString() };
  }, []);

  const blocks = useQuery({
    queryKey: ["time-blocks", range, filter],
    queryFn: () =>
      api<TimeBlock[]>("/time-blocks", { query: { ...range, professional_id: filter || undefined } }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api(`/time-blocks/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["time-blocks"] }),
  });

  const proName = (id: string | null) =>
    id ? (pros.data?.find((p) => p.id === id)?.name ?? "Profissional") : "Todo o estabelecimento";

  // Profissional só pode mexer na própria agenda; gestão e recepção em todas.
  const ownProId = pros.data?.find((p) => p.user_id === session?.user.id)?.id;
  const canManageAll = can(...MANAGERS, "receptionist");
  const canDelete = (b: TimeBlock) => canManageAll || (!!ownProId && b.professional_id === ownProId);

  return (
    <>
      <PageHeader
        title="Bloqueios de agenda"
        description={`Folgas, férias, feriados e compromissos dos próximos ${DAYS_AHEAD} dias.`}
        actions={
          (canManageAll || ownProId) && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" /> Novo bloqueio
            </Button>
          )
        }
      />
      <div className="mb-3 max-w-xs">
        <Select aria-label="Filtrar por profissional" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">Todos os profissionais</option>
          {pros.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Select>
      </div>
      <Card>
        {blocks.isLoading ? (
          <Spinner />
        ) : !blocks.data?.length ? (
          <EmptyState title="Nenhum bloqueio no período" description="Horários bloqueados não aparecem como disponíveis para agendamento." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {blocks.data.map((b) => (
              <li key={b.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div>
                  <p className="font-medium">{proName(b.professional_id)}</p>
                  <p className="text-sm text-slate-500">
                    {formatDateTime(b.starts_at)} até {formatDateTime(b.ends_at)}
                    {b.reason && ` · ${b.reason}`}
                  </p>
                </div>
                {canDelete(b) && (
                  <Button variant="ghost" size="sm" aria-label="Remover bloqueio" loading={remove.isPending && remove.variables === b.id}
                    onClick={() => remove.mutate(b.id)}>
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Sheet open={creating} title="Novo bloqueio" onClose={() => setCreating(false)}>
        {creating && (
          <BlockForm
            ownProId={canManageAll ? undefined : ownProId}
            canBlockAll={can(...MANAGERS)}
            onDone={() => setCreating(false)}
          />
        )}
      </Sheet>
    </>
  );
}

function BlockForm({ ownProId, canBlockAll, onDone }: { ownProId?: string; canBlockAll: boolean; onDone: () => void }) {
  const qc = useQueryClient();
  const pros = useProfessionals();
  const today = new Date().toLocaleDateString("sv-SE"); // AAAA-MM-DD no fuso local
  const [form, setForm] = useState({
    professional_id: ownProId ?? "",
    allDay: false,
    startDate: today,
    startTime: "12:00",
    endDate: today,
    endTime: "13:00",
    reason: "",
  });
  const [localError, setLocalError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (body: object) => api<TimeBlock>("/time-blocks", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["time-blocks"] });
      onDone();
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // Horário digitado = horário local do navegador; vai para a API com fuso (ISO em UTC).
    const starts = new Date(`${form.startDate}T${form.allDay ? "00:00" : form.startTime}`);
    const ends = form.allDay
      ? new Date(new Date(`${form.endDate}T00:00`).getTime() + 86_400_000)
      : new Date(`${form.endDate}T${form.endTime}`);
    if (!(starts < ends)) return setLocalError("O fim precisa ser depois do início.");
    if (!form.professional_id && !canBlockAll) return setLocalError("Escolha o profissional.");
    setLocalError(null);
    create.mutate({
      professional_id: form.professional_id || null,
      starts_at: starts.toISOString(),
      ends_at: ends.toISOString(),
      reason: form.reason || null,
    });
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      {(localError || create.error) && (
        <Alert>{localError ?? (create.error instanceof ApiError ? create.error.message : "Erro ao salvar")}</Alert>
      )}
      <Field label="Agenda">
        {(id) => (
          <Select id={id} value={form.professional_id} disabled={!!ownProId}
            onChange={(e) => setForm({ ...form, professional_id: e.target.value })}>
            {canBlockAll && <option value="">Todo o estabelecimento</option>}
            {!canBlockAll && !ownProId && <option value="">Escolha...</option>}
            {pros.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        )}
      </Field>
      <Checkbox label="Dia inteiro" checked={form.allDay} onChange={(allDay) => setForm({ ...form, allDay })} />
      <div className="grid grid-cols-2 gap-3">
        <Field label="Início">
          {(id) => <Input id={id} type="date" required value={form.startDate}
            onChange={(e) => setForm({ ...form, startDate: e.target.value, endDate: e.target.value > form.endDate ? e.target.value : form.endDate })} />}
        </Field>
        {!form.allDay && (
          <Field label="Hora">
            {(id) => <Input id={id} type="time" required value={form.startTime} onChange={(e) => setForm({ ...form, startTime: e.target.value })} />}
          </Field>
        )}
        <Field label="Fim">
          {(id) => <Input id={id} type="date" required min={form.startDate} value={form.endDate} onChange={(e) => setForm({ ...form, endDate: e.target.value })} />}
        </Field>
        {!form.allDay && (
          <Field label="Hora">
            {(id) => <Input id={id} type="time" required value={form.endTime} onChange={(e) => setForm({ ...form, endTime: e.target.value })} />}
          </Field>
        )}
      </div>
      <Field label="Motivo" hint="Opcional. Ex.: Férias, Feriado, Curso.">
        {(id) => <Input id={id} maxLength={200} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />}
      </Field>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={create.isPending}>Bloquear</Button>
      </div>
    </form>
  );
}
