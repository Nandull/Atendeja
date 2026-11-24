import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { NICHE_LABEL, type Tenant } from "@/api/types";
import { Alert, Button, Card, Field, Input, PageHeader } from "@/components/ui";
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
    </>
  );
}
