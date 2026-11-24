/**
 * Página pública de agendamento: atendeja.com.br/<slug>.
 *
 * Feita para o celular: o cliente escolhe serviço, profissional (ou "sem
 * preferência"), dia e horário, informa nome e WhatsApp e pronto. Não usa
 * login nem o AuthProvider do painel.
 *
 * Todas as datas e horas aparecem no fuso do ESTABELECIMENTO, não do celular:
 * quem está viajando vê o horário em que precisa chegar.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarCheck,
  CalendarPlus,
  ChevronLeft,
  ChevronRight,
  Clock,
  MapPin,
  MessageCircle,
  Phone,
  User,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "@/api/client";
import type {
  PublicAvailability,
  PublicBooking,
  PublicBusiness,
  PublicProfessional,
  PublicService,
} from "@/api/types";
import { Alert, Button, Checkbox, Field, Input, Spinner, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";
import { formatDuration, formatMoney, formatPhone, whatsappLink } from "@/lib/format";

type Step = "service" | "professional" | "time" | "details" | "done";
const ANY = "any";

function useTzFormat(tz: string | undefined) {
  return useMemo(() => {
    const timeZone = tz ?? "America/Sao_Paulo";
    const time = new Intl.DateTimeFormat("pt-BR", { timeZone, hour: "2-digit", minute: "2-digit" });
    const long = new Intl.DateTimeFormat("pt-BR", {
      timeZone,
      weekday: "long",
      day: "numeric",
      month: "long",
    });
    const hour = new Intl.DateTimeFormat("en-US", { timeZone, hour: "numeric", hourCycle: "h23" });
    return {
      time: (iso: string) => time.format(new Date(iso)),
      long: (iso: string) => long.format(new Date(iso)),
      hour: (iso: string) => Number(hour.format(new Date(iso))),
    };
  }, [tz]);
}

// Datas "AAAA-MM-DD" tratadas como dia de calendário (sem fuso).
const addDays = (day: string, n: number) => {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
const dayLabel = (day: string) => {
  const d = new Date(`${day}T12:00:00Z`);
  return {
    weekday: d.toLocaleDateString("pt-BR", { weekday: "short", timeZone: "UTC" }).replace(".", ""),
    num: d.getUTCDate(),
    month: d.toLocaleDateString("pt-BR", { month: "short", timeZone: "UTC" }).replace(".", ""),
  };
};
const todayIn = (tz: string) => new Date().toLocaleDateString("sv-SE", { timeZone: tz });

function priceLabel(s: PublicService) {
  return s.price_varies ? `a partir de ${formatMoney(s.price_cents)}` : formatMoney(s.price_cents);
}

export function BookingPage() {
  const { slug = "" } = useParams();
  const business = useQuery({
    queryKey: ["public", slug],
    queryFn: () => api<PublicBusiness>(`/public/${slug}`),
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
  });

  const [step, setStep] = useState<Step>("service");
  const [service, setService] = useState<PublicService | null>(null);
  const [proId, setProId] = useState<string>(ANY);
  const [slot, setSlot] = useState<{ starts_at: string; professional_id: string } | null>(null);
  const [booking, setBooking] = useState<PublicBooking | null>(null);

  useEffect(() => {
    if (business.data) document.title = `Agendar em ${business.data.name}`;
  }, [business.data]);

  if (business.isLoading) {
    return (
      <Shell>
        <Spinner />
      </Shell>
    );
  }
  if (business.error || !business.data) {
    const notFound = business.error instanceof ApiError && business.error.status === 404;
    return (
      <Shell>
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm">
          <CalendarCheck className="mx-auto size-10 text-slate-300" />
          <h1 className="mt-3 text-lg font-semibold">
            {notFound ? "Página de agendamento não encontrada" : "Não foi possível carregar"}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {notFound
              ? "Confira o link com o estabelecimento."
              : "Verifique sua conexão e tente de novo."}
          </p>
        </div>
      </Shell>
    );
  }

  const biz = business.data;
  const professional = service?.professionals.find((p) => p.id === proId) ?? null;
  const slotPro = service?.professionals.find((p) => p.id === slot?.professional_id) ?? null;

  const pickService = (s: PublicService) => {
    setService(s);
    setSlot(null);
    if (s.professionals.length === 1) {
      setProId(s.professionals[0].id);
      setStep("time");
    } else {
      setProId(ANY);
      setStep("professional");
    }
  };

  const back = () => {
    if (step === "professional") setStep("service");
    if (step === "time") setStep(service && service.professionals.length > 1 ? "professional" : "service");
    if (step === "details") setStep("time");
  };

  return (
    <Shell>
      <BusinessHeader biz={biz} compact={step !== "service"} />

      {step !== "service" && step !== "done" && (
        <button
          type="button"
          onClick={back}
          className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-brand-700"
        >
          <ArrowLeft className="size-4" /> Voltar
        </button>
      )}

      {step !== "service" && step !== "done" && service && (
        <Summary
          biz={biz}
          service={service}
          professional={step === "details" ? slotPro : professional}
          slot={step === "details" ? slot : null}
        />
      )}

      {step === "service" && (
        <ServiceList biz={biz} onPick={pickService} />
      )}

      {step === "professional" && service && (
        <ProfessionalList
          service={service}
          onPick={(id) => {
            setProId(id);
            setSlot(null);
            setStep("time");
          }}
        />
      )}

      {step === "time" && service && (
        <TimePicker
          biz={biz}
          service={service}
          proId={proId}
          onPick={(s) => {
            setSlot(s);
            setStep("details");
          }}
        />
      )}

      {step === "details" && service && slot && (
        <DetailsForm
          slug={slug}
          service={service}
          proId={proId}
          slot={slot}
          onDone={(b) => {
            setBooking(b);
            setStep("done");
          }}
          onSlotTaken={() => {
            setSlot(null);
            setStep("time");
          }}
        />
      )}

      {step === "done" && booking && (
        <Confirmation
          biz={biz}
          booking={booking}
          onAgain={() => {
            setBooking(null);
            setService(null);
            setSlot(null);
            setStep("service");
          }}
        />
      )}

      <footer className="mt-10 pb-6 text-center text-xs text-slate-400">
        Agendamento online por <span className="font-semibold text-slate-500">AtendeJá</span>
      </footer>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-gradient-to-b from-brand-50 to-slate-50">
      <main className="mx-auto w-full max-w-lg px-4 pt-6">{children}</main>
    </div>
  );
}

function BusinessHeader({ biz, compact }: { biz: PublicBusiness; compact: boolean }) {
  const initials = biz.name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
  return (
    <header className={cn("mb-5 flex items-center gap-3", !compact && "flex-col text-center")}>
      <div
        className={cn(
          "grid shrink-0 place-items-center rounded-2xl bg-brand-700 font-semibold text-white shadow-sm",
          compact ? "size-10 text-sm" : "size-16 text-xl",
        )}
        aria-hidden
      >
        {initials}
      </div>
      <div className="min-w-0">
        <h1 className={cn("font-semibold text-slate-900", compact ? "truncate text-base" : "text-xl")}>
          {biz.name}
        </h1>
        {!compact && (
          <div className="mt-1 space-y-0.5 text-sm text-slate-600">
            {biz.address && (
              <p className="flex items-center justify-center gap-1">
                <MapPin className="size-3.5 shrink-0" /> {biz.address}
              </p>
            )}
            {biz.phone && (
              <p className="flex items-center justify-center gap-1">
                <Phone className="size-3.5 shrink-0" /> {formatPhone(biz.phone)}
              </p>
            )}
          </div>
        )}
      </div>
    </header>
  );
}

function Summary({
  biz,
  service,
  professional,
  slot,
}: {
  biz: PublicBusiness;
  service: PublicService;
  professional: PublicProfessional | null;
  slot: { starts_at: string } | null;
}) {
  const fmt = useTzFormat(biz.timezone);
  const price = professional ? formatMoney(professional.price_cents) : priceLabel(service);
  return (
    <div className="mb-4 rounded-xl border border-brand-100 bg-white px-4 py-3 text-sm shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-slate-900">{service.name}</p>
          <p className="text-slate-500">
            {formatDuration(service.duration_min)}
            {professional ? ` · com ${professional.name}` : ""}
          </p>
          {slot && (
            <p className="mt-1 font-medium text-brand-800 first-letter:uppercase">
              {fmt.long(slot.starts_at)}, às {fmt.time(slot.starts_at)}
            </p>
          )}
        </div>
        <span className="shrink-0 font-semibold text-slate-900">{price}</span>
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-3 text-sm font-semibold tracking-wide text-slate-500 uppercase">{children}</h2>;
}

function ServiceList({ biz, onPick }: { biz: PublicBusiness; onPick: (s: PublicService) => void }) {
  return (
    <section>
      {biz.note && (
        <p className="mb-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{biz.note}</p>
      )}
      <SectionTitle>Escolha o serviço</SectionTitle>
      {biz.services.length === 0 ? (
        <div className="rounded-xl bg-white p-6 text-center text-sm text-slate-500 shadow-xs">
          No momento não há serviços para agendar online.
          {biz.phone && (
            <a className="mt-2 block font-medium text-brand-700" href={whatsappLink(biz.phone)}>
              Fale com a gente pelo WhatsApp
            </a>
          )}
        </div>
      ) : (
        <ul className="space-y-2">
          {biz.services.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onPick(s)}
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left shadow-xs transition hover:border-brand-500 focus-visible:outline-2 focus-visible:outline-brand-600"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-slate-900">{s.name}</p>
                    {s.description && (
                      <p className="mt-0.5 line-clamp-2 text-sm text-slate-500">{s.description}</p>
                    )}
                    <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
                      <Clock className="size-3.5" /> {formatDuration(s.duration_min)}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm font-semibold text-slate-900">{priceLabel(s)}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ProfessionalList({ service, onPick }: { service: PublicService; onPick: (id: string) => void }) {
  const options = [
    { id: ANY, name: "Sem preferência", specialty: "Primeiro horário disponível", color: "#94a3b8", price: null },
    ...service.professionals.map((p) => ({ ...p, price: p.price_cents })),
  ];
  return (
    <section>
      <SectionTitle>Com quem?</SectionTitle>
      <ul className="space-y-2">
        {options.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              onClick={() => onPick(p.id)}
              className="flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left shadow-xs transition hover:border-brand-500"
            >
              <span
                className="grid size-10 shrink-0 place-items-center rounded-full text-sm font-semibold text-white"
                style={{ backgroundColor: p.color }}
                aria-hidden
              >
                {p.id === ANY ? <User className="size-5" /> : p.name[0]?.toUpperCase()}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-slate-900">{p.name}</span>
                {p.specialty && <span className="block truncate text-sm text-slate-500">{p.specialty}</span>}
              </span>
              {p.price !== null && service.price_varies && (
                <span className="text-sm font-semibold">{formatMoney(p.price)}</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function TimePicker({
  biz,
  service,
  proId,
  onPick,
}: {
  biz: PublicBusiness;
  service: PublicService;
  proId: string;
  onPick: (s: { starts_at: string; professional_id: string }) => void;
}) {
  const fmt = useTzFormat(biz.timezone);
  const today = todayIn(biz.timezone);
  const lastDay = addDays(today, biz.window_days);
  const [weekStart, setWeekStart] = useState(today);
  const [selected, setSelected] = useState<string | null>(null);

  const avail = useQuery({
    queryKey: ["public", biz.slug, "availability", service.id, proId, weekStart],
    queryFn: () =>
      api<PublicAvailability>(`/public/${biz.slug}/availability`, {
        query: {
          service_id: service.id,
          professional_id: proId === ANY ? undefined : proId,
          start: weekStart,
          days: 7,
        },
      }),
    staleTime: 30_000,
  });

  const days = avail.data?.days ?? [];
  // Ao trocar de semana, seleciona o primeiro dia com horário.
  useEffect(() => {
    if (!avail.data) return;
    const current = avail.data.days.find((d) => d.date === selected && d.slots.length);
    if (!current) setSelected(avail.data.days.find((d) => d.slots.length)?.date ?? null);
  }, [avail.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const day = days.find((d) => d.date === selected);
  const groups = useMemo(() => {
    const out: { label: string; slots: NonNullable<typeof day>["slots"] }[] = [
      { label: "Manhã", slots: [] },
      { label: "Tarde", slots: [] },
      { label: "Noite", slots: [] },
    ];
    for (const s of day?.slots ?? []) {
      const h = fmt.hour(s.starts_at);
      out[h < 12 ? 0 : h < 18 ? 1 : 2].slots.push(s);
    }
    return out.filter((g) => g.slots.length);
  }, [day, fmt]);

  const canPrev = weekStart > today;
  const canNext = addDays(weekStart, 7) <= lastDay;
  const noneThisWeek = avail.data && days.every((d) => !d.slots.length);

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <SectionTitle>Escolha o dia</SectionTitle>
        <div className="-mt-3 flex gap-1">
          <button
            type="button"
            aria-label="Semana anterior"
            disabled={!canPrev}
            onClick={() => setWeekStart(addDays(weekStart, -7) < today ? today : addDays(weekStart, -7))}
            className="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white disabled:opacity-40"
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            type="button"
            aria-label="Próxima semana"
            disabled={!canNext}
            onClick={() => setWeekStart(addDays(weekStart, 7))}
            className="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white disabled:opacity-40"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1.5">
        {(avail.data ? days : Array.from({ length: 7 }, (_, i) => ({ date: addDays(weekStart, i), slots: [] }))).map(
          (d) => {
            const l = dayLabel(d.date);
            const free = d.slots.length > 0;
            const active = d.date === selected;
            return (
              <button
                key={d.date}
                type="button"
                disabled={!free}
                onClick={() => setSelected(d.date)}
                aria-pressed={active}
                aria-label={`${l.weekday} ${l.num} de ${l.month}${free ? "" : ", sem horários"}`}
                className={cn(
                  "flex flex-col items-center rounded-xl border py-2 text-xs transition",
                  active
                    ? "border-brand-700 bg-brand-700 text-white"
                    : free
                      ? "border-slate-200 bg-white text-slate-700 hover:border-brand-500"
                      : "border-transparent bg-slate-100 text-slate-400",
                )}
              >
                <span className="capitalize">{l.weekday}</span>
                <span className="text-base font-semibold">{l.num}</span>
                <span className="capitalize">{l.month}</span>
              </button>
            );
          },
        )}
      </div>

      <div className="mt-5">
        {avail.isLoading && <Spinner label="Buscando horários..." />}
        {avail.error && <Alert>{(avail.error as Error).message}</Alert>}
        {noneThisWeek && (
          <p className="rounded-xl bg-white p-5 text-center text-sm text-slate-500 shadow-xs">
            Sem horários livres nesta semana.
            {canNext && (
              <button
                type="button"
                className="mt-2 block w-full font-medium text-brand-700"
                onClick={() => setWeekStart(addDays(weekStart, 7))}
              >
                Ver a próxima semana
              </button>
            )}
          </p>
        )}
        {day && (
          <>
            <p className="mb-3 text-sm font-medium text-slate-700 first-letter:uppercase">
              {fmt.long(day.slots[0].starts_at)}
            </p>
            <div className="space-y-4">
              {groups.map((g) => (
                <div key={g.label}>
                  <p className="mb-2 text-xs font-medium text-slate-500">{g.label}</p>
                  <div className="grid grid-cols-4 gap-2">
                    {g.slots.map((s) => (
                      <button
                        key={s.starts_at}
                        type="button"
                        onClick={() => onPick(s)}
                        className="h-10 rounded-lg border border-slate-200 bg-white text-sm font-medium text-slate-800 shadow-xs transition hover:border-brand-600 hover:bg-brand-50"
                      >
                        {fmt.time(s.starts_at)}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function DetailsForm({
  slug,
  service,
  proId,
  slot,
  onDone,
  onSlotTaken,
}: {
  slug: string;
  service: PublicService;
  proId: string;
  slot: { starts_at: string; professional_id: string };
  onDone: (b: PublicBooking) => void;
  onSlotTaken: () => void;
}) {
  const [form, setForm] = useState({ name: "", phone: "", email: "", notes: "", consent: false, website: "" });
  const phoneDigits = form.phone.replace(/\D/g, "");
  const phoneOk = phoneDigits.length === 10 || phoneDigits.length === 11;

  const submit = useMutation({
    mutationFn: () =>
      api<PublicBooking>(`/public/${slug}/appointments`, {
        method: "POST",
        body: {
          service_id: service.id,
          // "Sem preferência" manda o profissional sugerido pelo horário; se ele
          // tiver sido ocupado nesse meio tempo, a API tenta os outros.
          professional_id: proId === ANY ? null : proId,
          starts_at: slot.starts_at,
          name: form.name,
          phone: phoneDigits,
          email: form.email || null,
          notes: form.notes || null,
          marketing_consent: form.consent,
          website: form.website || null,
        },
      }),
    onSuccess: onDone,
  });
  const taken = submit.error instanceof ApiError && submit.error.status === 409;

  return (
    <section>
      <SectionTitle>Seus dados</SectionTitle>
      <form
        className="space-y-4 rounded-2xl bg-white p-4 shadow-xs"
        onSubmit={(e) => {
          e.preventDefault();
          submit.mutate();
        }}
      >
        {submit.error && (
          <div className="space-y-2">
            <Alert>{(submit.error as Error).message}</Alert>
            {taken && (
              <Button type="button" variant="secondary" className="w-full" onClick={onSlotTaken}>
                Escolher outro horário
              </Button>
            )}
          </div>
        )}
        <Field label="Nome completo">
          {(id) => (
            <Input
              id={id}
              required
              minLength={2}
              maxLength={120}
              autoComplete="name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          )}
        </Field>
        <Field
          label="WhatsApp"
          hint="Para o estabelecimento confirmar o seu horário."
          error={form.phone && !phoneOk ? "Informe DDD + número." : undefined}
        >
          {(id) => (
            <Input
              id={id}
              required
              type="tel"
              inputMode="tel"
              autoComplete="tel-national"
              placeholder="(21) 99999-0000"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: formatPhone(e.target.value) })}
            />
          )}
        </Field>
        <Field label="E-mail (opcional)">
          {(id) => (
            <Input
              id={id}
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          )}
        </Field>
        <Field label="Observação (opcional)">
          {(id) => (
            <Textarea
              id={id}
              maxLength={500}
              placeholder="Alguma informação importante para o atendimento?"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          )}
        </Field>
        {/* Armadilha para robôs: invisível para pessoas. */}
        <div aria-hidden className="absolute -left-[9999px] size-px overflow-hidden">
          <label>
            Site
            <input
              tabIndex={-1}
              autoComplete="off"
              value={form.website}
              onChange={(e) => setForm({ ...form, website: e.target.value })}
            />
          </label>
        </div>
        <Checkbox
          label="Quero receber novidades e promoções"
          checked={form.consent}
          onChange={(consent) => setForm({ ...form, consent })}
        />
        <Button type="submit" className="h-12 w-full text-base" loading={submit.isPending} disabled={!phoneOk}>
          Confirmar agendamento
        </Button>
        <p className="text-center text-xs text-slate-400">
          Seus dados são usados só para este atendimento.
        </p>
      </form>
    </section>
  );
}

function icsFile(b: PublicBooking) {
  const stamp = (iso: string) => new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const esc = (t: string) => t.replace(/[,;\\]/g, (c) => `\\${c}`).replace(/\n/g, "\\n");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//AtendeJa//Agendamento//PT-BR",
    "BEGIN:VEVENT",
    `UID:${b.id}@atendeja`,
    `DTSTAMP:${stamp(new Date().toISOString())}`,
    `DTSTART:${stamp(b.starts_at)}`,
    `DTEND:${stamp(b.ends_at)}`,
    `SUMMARY:${esc(`${b.service} - ${b.business_name}`)}`,
    `DESCRIPTION:${esc(`Com ${b.professional}`)}`,
    ...(b.business_address ? [`LOCATION:${esc(b.business_address)}`] : []),
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return URL.createObjectURL(new Blob([lines.join("\r\n")], { type: "text/calendar" }));
}

function Confirmation({ biz, booking, onAgain }: { biz: PublicBusiness; booking: PublicBooking; onAgain: () => void }) {
  const fmt = useTzFormat(booking.timezone);
  const when = `${fmt.long(booking.starts_at)}, às ${fmt.time(booking.starts_at)}`;
  const icsUrl = useMemo(() => icsFile(booking), [booking]);
  useEffect(() => () => URL.revokeObjectURL(icsUrl), [icsUrl]);
  const message =
    `Olá! Acabei de agendar pelo link: ${booking.service} com ${booking.professional}, ` +
    `${when}.`;

  return (
    <section className="rounded-2xl bg-white p-6 text-center shadow-sm">
      <div className="mx-auto grid size-14 place-items-center rounded-full bg-emerald-100">
        <CalendarCheck className="size-7 text-emerald-700" />
      </div>
      <h2 className="mt-3 text-lg font-semibold text-slate-900">Agendamento feito!</h2>
      <p className="mt-1 text-sm text-slate-500">Guarde estas informações.</p>

      <dl className="mt-5 space-y-2 rounded-xl bg-slate-50 p-4 text-left text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-slate-500">Serviço</dt>
          <dd className="text-right font-medium">{booking.service}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-slate-500">Profissional</dt>
          <dd className="text-right font-medium">{booking.professional}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-slate-500">Quando</dt>
          <dd className="text-right font-medium first-letter:uppercase">{when}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-slate-500">Valor</dt>
          <dd className="text-right font-medium">{formatMoney(booking.price_cents)}</dd>
        </div>
        {booking.business_address && (
          <div className="flex justify-between gap-3">
            <dt className="text-slate-500">Endereço</dt>
            <dd className="text-right font-medium">{booking.business_address}</dd>
          </div>
        )}
      </dl>
      {biz.note && <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{biz.note}</p>}

      <div className="mt-5 grid gap-2">
        <a
          href={icsUrl}
          download="agendamento.ics"
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white text-sm font-medium text-slate-800"
        >
          <CalendarPlus className="size-4" /> Adicionar à minha agenda
        </a>
        {booking.business_phone && (
          <a
            href={whatsappLink(booking.business_phone, message)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-emerald-600 text-sm font-medium text-white"
          >
            <MessageCircle className="size-4" /> Avisar pelo WhatsApp
          </a>
        )}
        <button type="button" onClick={onAgain} className="mt-1 text-sm font-medium text-brand-700">
          Fazer outro agendamento
        </button>
      </div>
      <p className="mt-4 text-xs text-slate-400">
        Precisa remarcar ou cancelar? Fale com {booking.business_name}
        {booking.business_phone ? ` pelo ${formatPhone(booking.business_phone)}` : ""}.
      </p>
    </section>
  );
}
