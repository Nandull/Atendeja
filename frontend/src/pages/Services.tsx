import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { useServices } from "@/api/hooks";
import type { Service } from "@/api/types";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Sheet,
  Spinner,
  Textarea,
} from "@/components/ui";
import { centsToInput, formatDuration, formatMoney, parseMoney } from "@/lib/format";

export function ServicesPage() {
  const { can } = useAuth();
  const isManager = can(...MANAGERS);
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Service | "new" | null>(null);
  const { data, isLoading } = useServices(showInactive);

  return (
    <>
      <PageHeader
        title="Serviços"
        description="O catálogo que aparece na agenda e, depois, no agendamento online."
        actions={
          isManager && (
            <Button onClick={() => setEditing("new")}>
              <Plus className="size-4" /> Novo serviço
            </Button>
          )
        }
      />
      <div className="mb-3">
        <Checkbox label="Mostrar desativados" checked={showInactive} onChange={setShowInactive} />
      </div>
      <Card>
        {isLoading ? (
          <Spinner />
        ) : !data?.length ? (
          <EmptyState
            title="Nenhum serviço cadastrado"
            description="Cadastre o que você oferece, com duração e preço. Exemplo: Limpeza de pele, 60 min, R$ 150,00."
            action={isManager && <Button onClick={() => setEditing("new")}>Cadastrar serviço</Button>}
          />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.map((s) => (
              <li key={s.id}>
                <button
                  disabled={!isManager}
                  onClick={() => setEditing(s)}
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50 disabled:cursor-default disabled:hover:bg-transparent"
                >
                  <div className="min-w-0">
                    <p className="font-medium">
                      {s.name} {!s.active && <Badge>Desativado</Badge>}
                    </p>
                    <p className="text-sm text-slate-500">
                      {formatDuration(s.duration_min)}
                      {s.buffer_min > 0 && ` + ${s.buffer_min} min de intervalo`}
                      {!s.online_booking && " · só pela recepção"}
                    </p>
                  </div>
                  <span className="font-semibold whitespace-nowrap">{formatMoney(s.price_cents)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Sheet
        open={editing !== null}
        title={editing === "new" ? "Novo serviço" : "Editar serviço"}
        onClose={() => setEditing(null)}
      >
        {editing !== null && (
          <ServiceForm key={editing === "new" ? "new" : editing.id} service={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
        )}
      </Sheet>
    </>
  );
}

function ServiceForm({ service, onDone }: { service: Service | null; onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: service?.name ?? "",
    description: service?.description ?? "",
    duration_min: String(service?.duration_min ?? 60),
    buffer_min: String(service?.buffer_min ?? 0),
    price: service ? centsToInput(service.price_cents) : "",
    online_booking: service?.online_booking ?? true,
    active: service?.active ?? true,
  });
  const [localError, setLocalError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (body: object) =>
      service
        ? api<Service>(`/services/${service.id}`, { method: "PATCH", body })
        : api<Service>("/services", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["services"] });
      qc.invalidateQueries({ queryKey: ["professionals"] });
      onDone();
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const price_cents = parseMoney(form.price);
    if (price_cents === null) return setLocalError("Preço inválido. Exemplo: 150,00");
    setLocalError(null);
    save.mutate({
      name: form.name,
      description: form.description || null,
      duration_min: Number(form.duration_min),
      buffer_min: Number(form.buffer_min),
      price_cents,
      online_booking: form.online_booking,
      ...(service ? { active: form.active } : {}),
    });
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      {(localError || save.error) && (
        <Alert>{localError ?? (save.error instanceof ApiError ? save.error.message : "Erro ao salvar")}</Alert>
      )}
      <Field label="Nome">
        {(id) => <Input id={id} required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
      </Field>
      <Field label="Descrição" hint="Aparece para o cliente no agendamento online.">
        {(id) => <Textarea id={id} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Duração (min)">
          {(id) => <Input id={id} type="number" min={5} max={720} step={5} required value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: e.target.value })} />}
        </Field>
        <Field label="Intervalo após (min)" hint="Limpeza, preparo.">
          {(id) => <Input id={id} type="number" min={0} max={240} step={5} value={form.buffer_min} onChange={(e) => setForm({ ...form, buffer_min: e.target.value })} />}
        </Field>
      </div>
      <Field label="Preço (R$)">
        {(id) => <Input id={id} inputMode="decimal" required placeholder="150,00" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />}
      </Field>
      <Checkbox
        label="Disponível no agendamento online"
        description="Desmarque para serviços que exigem avaliação antes."
        checked={form.online_booking}
        onChange={(v) => setForm({ ...form, online_booking: v })}
      />
      {service && (
        <Checkbox label="Serviço ativo" checked={form.active} onChange={(v) => setForm({ ...form, active: v })} />
      )}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={save.isPending}>Salvar</Button>
      </div>
    </form>
  );
}
