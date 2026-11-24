import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, ExternalLink } from "lucide-react";
import { useState } from "react";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { NICHE_LABEL, type Tenant } from "@/api/types";
import { Alert, Button, Card, Checkbox, Field, Input, PageHeader, Select, Textarea } from "@/components/ui";
import { formatPhone } from "@/lib/format";

export function SettingsPage() {
  const { session, can } = useAuth();
  const qc = useQueryClient();
  const editable = can(...MANAGERS);
  const tenant = session!.tenant;
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({
    name: tenant.name,
    phone: tenant.phone ? formatPhone(tenant.phone) : "",
    address: tenant.address ?? "",
  });

  const save = useMutation({
    mutationFn: () =>
      api<Tenant>("/tenant", {
        method: "PATCH",
        body: { name: form.name, phone: form.phone.replace(/\D/g, "") || null, address: form.address || null },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  return (
    <>
      <PageHeader title="Estabelecimento" description="Dados que aparecem para os seus clientes." />
      <Card className="p-5">
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          {save.error instanceof ApiError && <div className="sm:col-span-2"><Alert>{save.error.message}</Alert></div>}
          <fieldset disabled={!editable} className="contents">
            <Field label="Nome">
              {(id) => <Input id={id} required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
            </Field>
            <Field label="Telefone">
              {(id) => <Input id={id} inputMode="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: formatPhone(e.target.value) })} />}
            </Field>
            <Field label="Endereço" className="sm:col-span-2">
              {(id) => <Input id={id} maxLength={255} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />}
            </Field>
          </fieldset>
          <dl className="grid gap-3 text-sm sm:col-span-2 sm:grid-cols-3">
            <div><dt className="text-slate-500">Tipo de negócio</dt><dd className="font-medium">{NICHE_LABEL[tenant.niche] ?? tenant.niche}</dd></div>
            <div><dt className="text-slate-500">Endereço do link</dt><dd className="font-medium">/{tenant.slug}</dd></div>
            <div><dt className="text-slate-500">Fuso horário</dt><dd className="font-medium">{tenant.timezone}</dd></div>
          </dl>
          {editable && (
            <div className="flex items-center justify-end gap-3 sm:col-span-2">
              {saved && <span className="text-sm text-emerald-700">Salvo</span>}
              <Button type="submit" loading={save.isPending}>Salvar</Button>
            </div>
          )}
        </form>
      </Card>
      <BookingSettings tenant={tenant} editable={editable} />
    </>
  );
}

const NOTICE_OPTIONS = [
  [0, "Sem antecedência"],
  [30, "30 minutos"],
  [60, "1 hora"],
  [120, "2 horas"],
  [240, "4 horas"],
  [720, "12 horas"],
  [1440, "1 dia"],
  [2880, "2 dias"],
] as const;
const WINDOW_OPTIONS = [7, 15, 30, 60, 90] as const;

function BookingSettings({ tenant, editable }: { tenant: Tenant; editable: boolean }) {
  const qc = useQueryClient();
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const [form, setForm] = useState({
    enabled: tenant.booking_enabled,
    notice: tenant.booking_min_notice_min,
    window: tenant.booking_window_days,
    note: tenant.booking_note ?? "",
  });
  const link = `${window.location.origin}/${tenant.slug}`;

  const save = useMutation({
    mutationFn: () =>
      api<Tenant>("/tenant", {
        method: "PATCH",
        body: {
          booking_enabled: form.enabled,
          booking_min_notice_min: form.notice,
          booking_window_days: form.window,
          booking_note: form.note.trim() || null,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const copy = async () => {
    await navigator.clipboard?.writeText(link).catch(() => undefined);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card className="mt-6 p-5">
      <h2 className="text-base font-semibold">Agendamento online</h2>
      <p className="mt-0.5 text-sm text-slate-500">
        Seu link para colocar na bio do Instagram, no WhatsApp e no Google.
      </p>
      <div className="mt-4 flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:flex-row sm:items-center">
        <code className="min-w-0 flex-1 truncate text-sm text-brand-800">{link}</code>
        <div className="flex gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={copy}>
            {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            {copied ? "Copiado" : "Copiar"}
          </Button>
          <a
            href={`/${tenant.slug}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700"
          >
            <ExternalLink className="size-4" /> Abrir
          </a>
        </div>
      </div>
      <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        {save.error instanceof ApiError && <div className="sm:col-span-2"><Alert>{save.error.message}</Alert></div>}
        <fieldset disabled={!editable} className="contents">
          <div className="sm:col-span-2">
            <Checkbox
              label="Aceitar agendamentos pelo link"
              description="Desligado, o link mostra “página não encontrada”."
              checked={form.enabled}
              onChange={(enabled) => setForm({ ...form, enabled })}
            />
          </div>
          <Field label="Antecedência mínima" hint="Evita marcações em cima da hora.">
            {(id) => (
              <Select id={id} value={form.notice} onChange={(e) => setForm({ ...form, notice: Number(e.target.value) })}>
                {NOTICE_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Mostrar horários até" hint="Quantos dias à frente o cliente enxerga.">
            {(id) => (
              <Select id={id} value={form.window} onChange={(e) => setForm({ ...form, window: Number(e.target.value) })}>
                {WINDOW_OPTIONS.map((v) => <option key={v} value={v}>{v} dias</option>)}
              </Select>
            )}
          </Field>
          <Field label="Aviso na página (opcional)" className="sm:col-span-2" hint="Ex.: chegue 10 minutos antes; pagamento no Pix ou cartão.">
            {(id) => <Textarea id={id} maxLength={500} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />}
          </Field>
        </fieldset>
        <p className="text-xs text-slate-500 sm:col-span-2">
          Só aparecem no link os serviços marcados como “agendável online” e os profissionais ativos com expediente cadastrado.
        </p>
        {editable && (
          <div className="flex items-center justify-end gap-3 sm:col-span-2">
            {saved && <span className="text-sm text-emerald-700">Salvo</span>}
            <Button type="submit" loading={save.isPending}>Salvar</Button>
          </div>
        )}
      </form>
    </Card>
  );
}
