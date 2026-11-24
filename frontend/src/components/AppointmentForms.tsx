import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircle } from "lucide-react";
import { useState } from "react";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { useProfessionals } from "@/api/hooks";
import type { Appointment, AppointmentStatus, Client, Slots } from "@/api/types";
import { ClientPicker } from "@/components/ClientPicker";
import { StatusBadge } from "@/components/StatusBadge";
import { Alert, Button, Checkbox, Field, Input, Select, Spinner, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";
import {
  formatDate,
  formatDuration,
  formatMoney,
  formatPhone,
  formatTime,
  localDate,
  localTime,
  whatsappLink,
} from "@/lib/format";

function useInvalidateAgenda() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["appointments"] });
    qc.invalidateQueries({ queryKey: ["appointment"] });
    qc.invalidateQueries({ queryKey: ["availability"] });
    qc.invalidateQueries({ queryKey: ["client-history"] });
  };
}

/** Horários livres do dia como botões, mais campo manual para encaixe. */
function TimePicker({
  professionalId,
  serviceId,
  date,
  time,
  onTime,
  ignoreId,
}: {
  professionalId: string;
  serviceId: string;
  date: string;
  time: string;
  onTime: (t: string) => void;
  ignoreId?: string;
}) {
  const slots = useQuery({
    queryKey: ["availability", professionalId, serviceId, date],
    queryFn: () =>
      api<Slots>("/availability", { query: { professional_id: professionalId, service_id: serviceId, date } }),
    enabled: !!professionalId && !!serviceId && !!date,
  });
  const free = (slots.data?.slots ?? []).map((s) => localTime(new Date(s)));

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700">Horários livres</p>
      {!professionalId || !serviceId ? (
        <p className="text-sm text-slate-500">Escolha profissional e serviço.</p>
      ) : slots.isLoading ? (
        <Spinner label="Buscando horários..." />
      ) : slots.error ? (
        <Alert>{(slots.error as Error).message}</Alert>
      ) : free.length === 0 ? (
        <p className="text-sm text-slate-500">
          Nenhum horário livre neste dia{ignoreId ? " além do atual" : ""}.
        </p>
      ) : (
        <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-5">
          {free.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => onTime(t)}
              className={cn(
                "rounded-md border px-2 py-1.5 text-sm",
                t === time ? "border-brand-700 bg-brand-700 text-white" : "border-slate-300 hover:border-brand-600",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      )}
      <Field label="Ou digite o horário">
        {(id) => <Input id={id} type="time" className="w-32" value={time} onChange={(e) => onTime(e.target.value)} />}
      </Field>
    </div>
  );
}

export function NewAppointmentForm({
  initialStart,
  initialProfessionalId,
  onDone,
}: {
  initialStart?: Date;
  initialProfessionalId?: string;
  onDone: () => void;
}) {
  const { session, can } = useAuth();
  const invalidate = useInvalidateAgenda();
  const pros = useProfessionals();
  const isScheduler = can(...MANAGERS, "receptionist");
  const ownPro = pros.data?.find((p) => p.user_id === session?.user.id);

  const [client, setClient] = useState<Client | null>(null);
  const [professionalId, setProfessionalId] = useState(initialProfessionalId ?? "");
  const [serviceId, setServiceId] = useState("");
  const [date, setDate] = useState(localDate(initialStart ?? new Date()));
  const [time, setTime] = useState(initialStart ? localTime(initialStart) : "");
  const [allowOutside, setAllowOutside] = useState(false);
  const [notes, setNotes] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const proId = isScheduler ? professionalId : (ownPro?.id ?? "");
  const pro = pros.data?.find((p) => p.id === proId);
  const service = pro?.services.find((s) => s.service_id === serviceId);

  const create = useMutation({
    mutationFn: () =>
      api<Appointment>("/appointments", {
        method: "POST",
        body: {
          client_id: client!.id,
          professional_id: proId,
          service_id: serviceId,
          starts_at: new Date(`${date}T${time}`).toISOString(),
          notes: notes || null,
          allow_outside_hours: allowOutside,
        },
      }),
    onSuccess: () => {
      invalidate();
      onDone();
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!client) return setLocalError("Escolha o cliente.");
    if (!proId || !serviceId) return setLocalError("Escolha profissional e serviço.");
    if (!time) return setLocalError("Escolha o horário.");
    setLocalError(null);
    create.mutate();
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      {(localError || create.error) && (
        <Alert>{localError ?? (create.error instanceof ApiError ? create.error.message : "Erro ao agendar")}</Alert>
      )}
      <div className="space-y-1.5">
        <p className="text-sm font-medium text-slate-700">Cliente</p>
        <ClientPicker value={client} onChange={setClient} />
      </div>
      {isScheduler && (
        <Field label="Profissional">
          {(id) => (
            <Select id={id} value={professionalId} onChange={(e) => { setProfessionalId(e.target.value); setServiceId(""); }}>
              <option value="">Escolha...</option>
              {pros.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
          )}
        </Field>
      )}
      <Field label="Serviço">
        {(id) => (
          <Select id={id} value={serviceId} disabled={!pro} onChange={(e) => setServiceId(e.target.value)}>
            <option value="">{pro && !pro.services.length ? "Este profissional não tem serviços" : "Escolha..."}</option>
            {pro?.services.map((s) => (
              <option key={s.service_id} value={s.service_id}>
                {s.name} · {formatDuration(s.duration_min)} · {formatMoney(s.price_cents)}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Data">
        {(id) => <Input id={id} type="date" required value={date} onChange={(e) => setDate(e.target.value)} />}
      </Field>
      <TimePicker professionalId={proId} serviceId={serviceId} date={date} time={time} onTime={setTime} />
      {isScheduler && (
        <Checkbox label="Encaixe fora do expediente" description="Use quando o profissional aceitou atender fora do horário."
          checked={allowOutside} onChange={setAllowOutside} />
      )}
      <Field label="Observações">
        {(id) => <Textarea id={id} value={notes} onChange={(e) => setNotes(e.target.value)} />}
      </Field>
      {service && (
        <p className="text-sm text-slate-600">
          Valor: <span className="font-semibold">{formatMoney(service.price_cents)}</span>
        </p>
      )}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={create.isPending}>Agendar</Button>
      </div>
    </form>
  );
}

const ACTIONS: { status: AppointmentStatus; label: string; from: AppointmentStatus[]; needsStarted?: boolean; variant?: "secondary" | "danger" }[] = [
  { status: "confirmed", label: "Confirmar", from: ["scheduled"] },
  { status: "completed", label: "Marcar atendido", from: ["scheduled", "confirmed", "no_show"], needsStarted: true },
  { status: "no_show", label: "Marcar falta", from: ["scheduled", "confirmed", "completed"], needsStarted: true, variant: "secondary" },
];

export function AppointmentDetails({ id, onClose }: { id: string; onClose: () => void }) {
  const { session } = useAuth();
  const invalidate = useInvalidateAgenda();
  const [mode, setMode] = useState<"view" | "cancel" | "move">("view");
  const [reason, setReason] = useState("");
  const [moveDate, setMoveDate] = useState("");
  const [moveTime, setMoveTime] = useState("");
  const [allowOutside, setAllowOutside] = useState(false);

  const { data: a, isLoading } = useQuery({
    queryKey: ["appointment", id],
    queryFn: () => api<Appointment>(`/appointments/${id}`),
  });

  const setStatus = useMutation({
    mutationFn: (body: { status: AppointmentStatus; cancel_reason?: string }) =>
      api<Appointment>(`/appointments/${id}/status`, { method: "POST", body }),
    onSuccess: () => {
      invalidate();
      setMode("view");
    },
  });
  const reschedule = useMutation({
    mutationFn: () =>
      api<Appointment>(`/appointments/${id}`, {
        method: "PATCH",
        body: { starts_at: new Date(`${moveDate}T${moveTime}`).toISOString(), allow_outside_hours: allowOutside },
      }),
    onSuccess: () => {
      invalidate();
      setMode("view");
    },
  });

  if (isLoading || !a) return <Spinner />;
  const started = new Date(a.starts_at) <= new Date();
  const open = a.status === "scheduled" || a.status === "confirmed";
  const error = setStatus.error ?? reschedule.error;
  const confirmMsg =
    `Olá, ${a.client.name.split(" ")[0]}! Passando para confirmar seu horário de ${a.service.name} ` +
    `em ${formatDate(a.starts_at)} às ${formatTime(a.starts_at)} na ${session?.tenant.name}. Podemos confirmar?`;
  const isScheduler = session && ["owner", "admin", "receptionist"].includes(session.role);

  return (
    <div className="space-y-5">
      {error instanceof ApiError && <Alert>{error.message}</Alert>}
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold">{a.client.name}</p>
          <p className="text-sm text-slate-500">{formatPhone(a.client.phone)}</p>
        </div>
        <StatusBadge status={a.status} />
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-slate-500">Serviço</dt><dd className="font-medium">{a.service.name}</dd></div>
        <div><dt className="text-slate-500">Profissional</dt><dd className="font-medium">{a.professional.name}</dd></div>
        <div><dt className="text-slate-500">Data</dt><dd className="font-medium">{formatDate(a.starts_at)}</dd></div>
        <div><dt className="text-slate-500">Horário</dt><dd className="font-medium">{formatTime(a.starts_at)} às {formatTime(a.ends_at)}</dd></div>
        <div><dt className="text-slate-500">Valor</dt><dd className="font-medium">{formatMoney(a.price_cents)}</dd></div>
        <div><dt className="text-slate-500">Origem</dt><dd className="font-medium">{a.origin === "online" ? "Agendamento online" : "Recepção"}</dd></div>
      </dl>
      {a.notes && <p className="rounded-lg bg-slate-50 p-3 text-sm">{a.notes}</p>}
      {a.cancel_reason && <p className="text-sm text-slate-500">Motivo do cancelamento: {a.cancel_reason}</p>}

      {open && (
        <a href={whatsappLink(a.client.phone, confirmMsg)} target="_blank" rel="noreferrer"
          className="flex items-center justify-center gap-2 rounded-lg border border-emerald-600 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50">
          <MessageCircle className="size-4" /> Pedir confirmação pelo WhatsApp
        </a>
      )}

      {mode === "view" && (
        <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
          {ACTIONS.filter((x) => x.from.includes(a.status) && (!x.needsStarted || started)).map((x) => (
            <Button key={x.status} size="sm" variant={x.variant} loading={setStatus.isPending && setStatus.variables?.status === x.status}
              onClick={() => setStatus.mutate({ status: x.status })}>
              {x.label}
            </Button>
          ))}
          {open && (
            <>
              <Button size="sm" variant="secondary" onClick={() => {
                setMoveDate(localDate(new Date(a.starts_at)));
                setMoveTime(localTime(new Date(a.starts_at)));
                setMode("move");
              }}>Reagendar</Button>
              <Button size="sm" variant="danger" onClick={() => setMode("cancel")}>Cancelar</Button>
            </>
          )}
        </div>
      )}

      {mode === "cancel" && (
        <div className="space-y-3 border-t border-slate-200 pt-4">
          <Field label="Motivo do cancelamento" hint="Opcional. Ajuda a entender cancelamentos depois.">
            {(fid) => <Input id={fid} maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} />}
          </Field>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setMode("view")}>Voltar</Button>
            <Button size="sm" variant="danger" loading={setStatus.isPending}
              onClick={() => setStatus.mutate({ status: "canceled", cancel_reason: reason || undefined })}>
              Confirmar cancelamento
            </Button>
          </div>
        </div>
      )}

      {mode === "move" && (
        <div className="space-y-3 border-t border-slate-200 pt-4">
          <Field label="Nova data">
            {(fid) => <Input id={fid} type="date" value={moveDate} onChange={(e) => setMoveDate(e.target.value)} />}
          </Field>
          <TimePicker professionalId={a.professional.id} serviceId={a.service.id} date={moveDate} time={moveTime} onTime={setMoveTime} ignoreId={a.id} />
          {isScheduler && <Checkbox label="Encaixe fora do expediente" checked={allowOutside} onChange={setAllowOutside} />}
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setMode("view")}>Voltar</Button>
            <Button size="sm" loading={reschedule.isPending} onClick={() => reschedule.mutate()}>Salvar novo horário</Button>
          </div>
        </div>
      )}
      <div className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={onClose}>Fechar</Button>
      </div>
    </div>
  );
}
