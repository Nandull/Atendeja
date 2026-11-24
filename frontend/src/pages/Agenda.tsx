import type { DatesSetArg, EventClickArg, EventDropArg, EventInput } from "@fullcalendar/core";
import ptBrLocale from "@fullcalendar/core/locales/pt-br";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin, { type DateClickArg } from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { useProfessionals } from "@/api/hooks";
import type { Appointment, TimeBlock } from "@/api/types";
import { AppointmentDetails, NewAppointmentForm } from "@/components/AppointmentForms";
import { Alert, Button, Checkbox, PageHeader, Select, Sheet } from "@/components/ui";

type Range = { start: string; end: string };
type SheetState =
  | { kind: "new"; start?: Date; professionalId?: string }
  | { kind: "view"; id: string }
  | null;

const isMobile = () => window.matchMedia("(max-width: 767px)").matches;

export function AgendaPage() {
  const { session, can } = useAuth();
  const qc = useQueryClient();
  const pros = useProfessionals();
  const [range, setRange] = useState<Range | null>(null);
  const [proFilter, setProFilter] = useState("");
  const [showCanceled, setShowCanceled] = useState(false);
  const [sheet, setSheet] = useState<SheetState>(null);
  const [dropError, setDropError] = useState<string | null>(null);

  const isProfessional = session?.role === "professional";
  const canSchedule = can(...MANAGERS, "receptionist") || isProfessional;

  const appointments = useQuery({
    queryKey: ["appointments", range, proFilter, showCanceled],
    queryFn: () =>
      api<Appointment[]>("/appointments", {
        query: { ...range, professional_id: proFilter || undefined, include_canceled: showCanceled },
      }),
    enabled: !!range,
  });
  const blocks = useQuery({
    queryKey: ["time-blocks", range, proFilter],
    queryFn: () =>
      api<TimeBlock[]>("/time-blocks", { query: { ...range, professional_id: proFilter || undefined } }),
    enabled: !!range,
  });

  const move = useMutation({
    mutationFn: ({ id, starts_at }: { id: string; starts_at: string }) =>
      api<Appointment>(`/appointments/${id}`, { method: "PATCH", body: { starts_at } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["appointments"] }),
  });

  // Horário visível: do expediente mais cedo ao mais tarde (com folga de 1h).
  const { minTime, maxTime } = useMemo(() => {
    const hours = pros.data?.flatMap((p) => p.working_hours) ?? [];
    if (!hours.length) return { minTime: "07:00:00", maxTime: "21:00:00" };
    const min = hours.reduce((m, h) => (h.start_time < m ? h.start_time : m), "23:59:59");
    const max = hours.reduce((m, h) => (h.end_time > m ? h.end_time : m), "00:00:00");
    const pad = (t: string, d: number) => `${String(Math.min(24, Math.max(0, Number(t.slice(0, 2)) + d))).padStart(2, "0")}:00:00`;
    return { minTime: pad(min, -1), maxTime: pad(max, max.slice(3, 5) === "00" ? 1 : 2) };
  }, [pros.data]);

  const events: EventInput[] = useMemo(() => {
    const appts: EventInput[] = (appointments.data ?? []).map((a) => ({
      id: a.id,
      title: `${a.client.name} · ${a.service.name}`,
      start: a.starts_at,
      end: a.ends_at,
      backgroundColor: a.status === "canceled" || a.status === "completed" ? "#e2e8f0" : a.professional.color,
      borderColor: a.status === "no_show" ? "#dc2626" : a.professional.color,
      textColor: a.status === "canceled" || a.status === "completed" ? "#334155" : "#ffffff",
      classNames: [`st-${a.status}`],
      editable: a.status === "scheduled" || a.status === "confirmed",
      extendedProps: { professional: a.professional.name },
    }));
    const bg: EventInput[] = (blocks.data ?? []).map((b) => ({
      id: `block-${b.id}`,
      start: b.starts_at,
      end: b.ends_at,
      display: "background",
      backgroundColor: "#94a3b8",
      title: b.reason ?? "Bloqueado",
    }));
    return [...appts, ...bg];
  }, [appointments.data, blocks.data]);

  return (
    <>
      <PageHeader
        title="Agenda"
        actions={
          canSchedule && (
            <Button onClick={() => setSheet({ kind: "new", professionalId: proFilter || undefined })}>
              <Plus className="size-4" /> Novo agendamento
            </Button>
          )
        }
      />
      <div className="mb-3 flex flex-wrap items-center gap-4">
        {!isProfessional && (
          <Select aria-label="Filtrar por profissional" className="w-56" value={proFilter} onChange={(e) => setProFilter(e.target.value)}>
            <option value="">Todos os profissionais</option>
            {pros.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        )}
        <Checkbox label="Mostrar cancelados" checked={showCanceled} onChange={setShowCanceled} />
        {!isProfessional && !!pros.data?.length && (
          <div className="flex flex-wrap gap-3 text-xs text-slate-600">
            {pros.data.map((p) => (
              <span key={p.id} className="flex items-center gap-1">
                <span className="size-2.5 rounded-full" style={{ backgroundColor: p.color }} /> {p.name}
              </span>
            ))}
          </div>
        )}
      </div>
      {dropError && <div className="mb-3"><Alert>{dropError}</Alert></div>}

      <div className="agenda rounded-xl border border-slate-200 bg-white p-2 shadow-xs sm:p-4">
        <FullCalendar
          plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]}
          locale={ptBrLocale}
          initialView={isMobile() ? "timeGridDay" : "timeGridWeek"}
          headerToolbar={{ left: "prev,next today", center: "title", right: "timeGridDay,timeGridWeek,dayGridMonth" }}
          height="auto"
          allDaySlot={false}
          nowIndicator
          slotMinTime={minTime}
          slotMaxTime={maxTime}
          slotDuration="00:15:00"
          slotLabelInterval="01:00"
          expandRows
          eventDurationEditable={false}
          editable={canSchedule}
          events={events}
          datesSet={(arg: DatesSetArg) => setRange({ start: arg.start.toISOString(), end: arg.end.toISOString() })}
          dateClick={(arg: DateClickArg) => {
            if (!canSchedule) return;
            if (arg.view.type === "dayGridMonth") return arg.view.calendar.changeView("timeGridDay", arg.date);
            setSheet({ kind: "new", start: arg.date, professionalId: proFilter || undefined });
          }}
          eventClick={(arg: EventClickArg) => {
            if (arg.event.display === "background") return;
            setSheet({ kind: "view", id: arg.event.id });
          }}
          eventDrop={(arg: EventDropArg) => {
            setDropError(null);
            move.mutate(
              { id: arg.event.id, starts_at: arg.event.start!.toISOString() },
              {
                onError: (e) => {
                  arg.revert();
                  setDropError(e instanceof ApiError ? e.message : "Não foi possível reagendar.");
                },
              },
            );
          }}
        />
      </div>

      <Sheet
        open={sheet !== null}
        title={sheet?.kind === "view" ? "Agendamento" : "Novo agendamento"}
        onClose={() => setSheet(null)}
      >
        {sheet?.kind === "new" && (
          <NewAppointmentForm
            key={`${sheet.start?.toISOString()}-${sheet.professionalId}`}
            initialStart={sheet.start}
            initialProfessionalId={sheet.professionalId}
            onDone={() => setSheet(null)}
          />
        )}
        {sheet?.kind === "view" && <AppointmentDetails id={sheet.id} onClose={() => setSheet(null)} />}
      </Sheet>
    </>
  );
}
