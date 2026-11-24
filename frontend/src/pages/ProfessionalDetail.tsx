import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Copy, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { useMembers, useServices } from "@/api/hooks";
import { WEEKDAYS, type Professional, type WorkingHour } from "@/api/types";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Field,
  Input,
  Select,
  Spinner,
} from "@/components/ui";
import { centsToInput, formatDuration, formatMoney, hhmm, parseMoney } from "@/lib/format";
import { ColorPicker } from "./Professionals";

function useSaved() {
  const [saved, setSaved] = useState(false);
  return {
    saved,
    flash: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  };
}

export function ProfessionalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["professional", id],
    queryFn: () => api<Professional>(`/professionals/${id}`),
  });

  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert>Profissional não encontrado.</Alert>;

  return (
    <>
      <Link to="/profissionais" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft className="size-4" /> Profissionais
      </Link>
      <div className="mb-6 flex items-center gap-3">
        <span className="size-4 rounded-full" style={{ backgroundColor: data.color }} aria-hidden />
        <h1 className="text-2xl font-semibold tracking-tight">{data.name}</h1>
      </div>
      <div className="space-y-6">
        <DetailsSection pro={data} />
        <ServicesSection pro={data} />
        <HoursSection pro={data} />
      </div>
    </>
  );
}

function useRefresh(id: string) {
  const qc = useQueryClient();
  return (p: Professional) => {
    qc.setQueryData(["professional", id], p);
    qc.invalidateQueries({ queryKey: ["professionals"] });
  };
}

function DetailsSection({ pro }: { pro: Professional }) {
  const { can } = useAuth();
  const editable = can(...MANAGERS);
  const members = useMembers();
  const refresh = useRefresh(pro.id);
  const { saved, flash } = useSaved();
  const [form, setForm] = useState({
    name: pro.name,
    specialty: pro.specialty ?? "",
    color: pro.color,
    user_id: pro.user_id ?? "",
    active: pro.active,
  });

  const save = useMutation({
    mutationFn: () =>
      api<Professional>(`/professionals/${pro.id}`, {
        method: "PATCH",
        body: { ...form, specialty: form.specialty || null, user_id: form.user_id || null },
      }),
    onSuccess: (p) => {
      refresh(p);
      flash();
    },
  });

  return (
    <Card className="p-5">
      <h2 className="mb-4 font-semibold">Dados</h2>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        {save.error instanceof ApiError && <div className="sm:col-span-2"><Alert>{save.error.message}</Alert></div>}
        <fieldset disabled={!editable} className="contents">
          <Field label="Nome">
            {(id) => <Input id={id} required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
          </Field>
          <Field label="Especialidade">
            {(id) => <Input id={id} value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} />}
          </Field>
          <Field label="Login do profissional" hint="Ligue a um usuário da equipe para ele ver a própria agenda.">
            {(id) => (
              <Select id={id} value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })}>
                <option value="">Sem login</option>
                {members.data?.map((m) => (
                  <option key={m.user_id} value={m.user_id}>{m.name} ({m.email})</option>
                ))}
              </Select>
            )}
          </Field>
          <div className="space-y-3">
            <ColorPicker value={form.color} onChange={(color) => setForm({ ...form, color })} />
            <Checkbox label="Ativo" checked={form.active} onChange={(active) => setForm({ ...form, active })} />
          </div>
        </fieldset>
        {editable && (
          <div className="flex items-center justify-end gap-3 sm:col-span-2">
            {saved && <span className="text-sm text-emerald-700">Salvo</span>}
            <Button type="submit" loading={save.isPending}>Salvar dados</Button>
          </div>
        )}
      </form>
    </Card>
  );
}

function ServicesSection({ pro }: { pro: Professional }) {
  const { can } = useAuth();
  const editable = can(...MANAGERS);
  const services = useServices();
  const refresh = useRefresh(pro.id);
  const { saved, flash } = useSaved();
  const [selected, setSelected] = useState<Record<string, string | null>>(() =>
    Object.fromEntries(
      pro.services.map((s) => [
        s.service_id,
        s.price_cents_override !== null ? centsToInput(s.price_cents_override) : null,
      ]),
    ),
  );
  const [localError, setLocalError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (body: object) =>
      api<Professional>(`/professionals/${pro.id}/services`, { method: "PUT", body }),
    onSuccess: (p) => {
      refresh(p);
      flash();
    },
  });

  function submit() {
    const body = [];
    for (const [service_id, price] of Object.entries(selected)) {
      let price_cents_override: number | null = null;
      if (price) {
        price_cents_override = parseMoney(price);
        if (price_cents_override === null) return setLocalError("Preço próprio inválido. Exemplo: 180,00");
      }
      body.push({ service_id, price_cents_override });
    }
    setLocalError(null);
    save.mutate(body);
  }

  if (services.isLoading) return <Card className="p-5"><Spinner /></Card>;

  return (
    <Card className="p-5">
      <h2 className="font-semibold">Serviços que realiza</h2>
      <p className="mb-4 text-sm text-slate-500">Preço próprio é opcional: use quando este profissional cobra diferente do catálogo.</p>
      {(localError || save.error) && (
        <div className="mb-3"><Alert>{localError ?? (save.error as Error).message}</Alert></div>
      )}
      {!services.data?.length ? (
        <p className="text-sm text-slate-500">
          Nenhum serviço no catálogo. <Link to="/servicos" className="text-brand-700 hover:underline">Cadastre os serviços</Link> primeiro.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {services.data.map((s) => {
            const checked = s.id in selected;
            return (
              <li key={s.id} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-48 flex-1">
                  <Checkbox
                    label={s.name}
                    description={`${formatDuration(s.duration_min)} · ${formatMoney(s.price_cents)}`}
                    checked={checked}
                    onChange={(v) =>
                      editable &&
                      setSelected((cur) => {
                        const next = { ...cur };
                        if (v) next[s.id] = null;
                        else delete next[s.id];
                        return next;
                      })
                    }
                  />
                </div>
                {checked && (
                  <Input
                    aria-label={`Preço próprio para ${s.name}`}
                    className="w-36"
                    inputMode="decimal"
                    placeholder="Preço próprio"
                    disabled={!editable}
                    value={selected[s.id] ?? ""}
                    onChange={(e) => setSelected({ ...selected, [s.id]: e.target.value || null })}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
      {editable && !!services.data?.length && (
        <div className="mt-4 flex items-center justify-end gap-3">
          {saved && <span className="text-sm text-emerald-700">Salvo</span>}
          <Button onClick={submit} loading={save.isPending}>Salvar serviços</Button>
        </div>
      )}
    </Card>
  );
}

type Range = { start: string; end: string };

function HoursSection({ pro }: { pro: Professional }) {
  const { can } = useAuth();
  const editable = can(...MANAGERS);
  const qc = useQueryClient();
  const { saved, flash } = useSaved();
  const [week, setWeek] = useState<Range[][]>(() =>
    WEEKDAYS.map((_, day) =>
      pro.working_hours
        .filter((h) => h.weekday === day)
        .map((h) => ({ start: hhmm(h.start_time), end: hhmm(h.end_time) })),
    ),
  );

  const save = useMutation({
    mutationFn: (body: WorkingHour[]) =>
      api<WorkingHour[]>(`/professionals/${pro.id}/working-hours`, { method: "PUT", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["professional", pro.id] });
      qc.invalidateQueries({ queryKey: ["professionals"] });
      flash();
    },
  });

  const update = (day: number, fn: (ranges: Range[]) => Range[]) =>
    setWeek((w) => w.map((r, i) => (i === day ? fn(r) : r)));

  const copyToWeekdays = (day: number) =>
    setWeek((w) => w.map((r, i) => (i < 5 ? w[day].map((x) => ({ ...x })) : r)));

  return (
    <Card className="p-5">
      <h2 className="font-semibold">Expediente semanal</h2>
      <p className="mb-4 text-sm text-slate-500">Use duas faixas no mesmo dia para separar o almoço.</p>
      {save.error instanceof ApiError && <div className="mb-3"><Alert>{save.error.message}</Alert></div>}
      <div className="divide-y divide-slate-100">
        {WEEKDAYS.map((label, day) => (
          <div key={label} className="flex flex-wrap items-start gap-3 py-3">
            <div className="w-28 pt-2">
              <Checkbox
                label={label}
                checked={week[day].length > 0}
                onChange={(v) => editable && update(day, () => (v ? [{ start: "08:00", end: "18:00" }] : []))}
              />
            </div>
            <div className="flex flex-1 flex-col gap-2">
              {week[day].length === 0 && <span className="pt-2 text-sm text-slate-400">Não atende</span>}
              {week[day].map((r, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input type="time" aria-label={`${label} início`} className="w-32" disabled={!editable} value={r.start}
                    onChange={(e) => update(day, (rs) => rs.map((x, j) => (j === i ? { ...x, start: e.target.value } : x)))} />
                  <span className="text-sm text-slate-500">às</span>
                  <Input type="time" aria-label={`${label} fim`} className="w-32" disabled={!editable} value={r.end}
                    onChange={(e) => update(day, (rs) => rs.map((x, j) => (j === i ? { ...x, end: e.target.value } : x)))} />
                  {editable && (
                    <Button type="button" variant="ghost" size="sm" aria-label="Remover faixa"
                      onClick={() => update(day, (rs) => rs.filter((_, j) => j !== i))}>
                      <Trash2 className="size-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
            {editable && week[day].length > 0 && (
              <div className="flex gap-1">
                <Button type="button" variant="ghost" size="sm"
                  onClick={() => update(day, (rs) => [...rs, { start: "13:00", end: "18:00" }])}>
                  <Plus className="size-4" /> Faixa
                </Button>
                {day === 0 && (
                  <Button type="button" variant="ghost" size="sm" onClick={() => copyToWeekdays(0)}>
                    <Copy className="size-4" /> Copiar para seg-sex
                  </Button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      {editable && (
        <div className="mt-4 flex items-center justify-end gap-3">
          {saved && <span className="text-sm text-emerald-700">Salvo</span>}
          <Button
            loading={save.isPending}
            onClick={() =>
              save.mutate(
                week.flatMap((ranges, weekday) =>
                  ranges.map((r) => ({ weekday, start_time: r.start, end_time: r.end })),
                ),
              )
            }
          >
            Salvar expediente
          </Button>
        </div>
      )}
    </Card>
  );
}
