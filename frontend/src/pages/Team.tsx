import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { useMembers } from "@/api/hooks";
import { ROLE_LABEL, type Member, type Role } from "@/api/types";
import { Alert, Button, Card, Field, Input, PageHeader, Select, Sheet, Spinner } from "@/components/ui";

const ROLE_HELP: Record<Role, string> = {
  owner: "Acesso total, inclusive assinatura e equipe.",
  admin: "Gerencia cadastros e equipe, exceto o dono.",
  receptionist: "Agenda, clientes e bloqueios.",
  professional: "Consulta e a própria agenda.",
};

export function TeamPage() {
  const { session, can } = useAuth();
  const isManager = can(...MANAGERS);
  const isOwner = can("owner");
  const qc = useQueryClient();
  const { data, isLoading } = useMembers();
  const [adding, setAdding] = useState(false);

  const changeRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: Role }) =>
      api<Member>(`/members/${id}`, { method: "PATCH", body: { role } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["members"] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/members/${id}`, { method: "DELETE" }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["members"] }),
  });
  const error = changeRole.error ?? remove.error;
  const roles = (Object.keys(ROLE_LABEL) as Role[]).filter((r) => isOwner || r !== "owner");

  return (
    <>
      <PageHeader
        title="Equipe e acessos"
        description="Quem pode entrar no sistema e o que cada um pode fazer."
        actions={isManager && <Button onClick={() => setAdding(true)}><Plus className="size-4" /> Adicionar pessoa</Button>}
      />
      {error instanceof ApiError && <div className="mb-3"><Alert>{error.message}</Alert></div>}
      <Card>
        {isLoading ? (
          <Spinner />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data?.map((m) => {
              const self = m.user_id === session?.user.id;
              const locked = !isManager || self || (m.role === "owner" && !isOwner);
              return (
                <li key={m.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{m.name} {self && <span className="text-sm text-slate-500">(você)</span>}</p>
                    <p className="truncate text-sm text-slate-500">{m.email}</p>
                  </div>
                  {locked ? (
                    <span className="text-sm text-slate-600">{ROLE_LABEL[m.role]}</span>
                  ) : (
                    <Select aria-label={`Perfil de ${m.name}`} className="w-40" value={m.role}
                      onChange={(e) => changeRole.mutate({ id: m.id, role: e.target.value as Role })}>
                      {roles.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                    </Select>
                  )}
                  {!locked && (
                    <Button variant="ghost" size="sm" aria-label={`Remover ${m.name}`}
                      onClick={() => window.confirm(`Remover ${m.name} da equipe?`) && remove.mutate(m.id)}>
                      <Trash2 className="size-4" />
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>
      <Card className="mt-6 p-5">
        <h2 className="mb-3 font-semibold">Perfis de acesso</h2>
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
            <div key={r}>
              <dt className="font-medium">{ROLE_LABEL[r]}</dt>
              <dd className="text-slate-500">{ROLE_HELP[r]}</dd>
            </div>
          ))}
        </dl>
      </Card>
      <Sheet open={adding} title="Adicionar pessoa" onClose={() => setAdding(false)}>
        {adding && <AddMemberForm roles={roles} onDone={() => setAdding(false)} />}
      </Sheet>
    </>
  );
}

function AddMemberForm({ roles, onDone }: { roles: Role[]; onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: "", email: "", role: "receptionist" as Role, password: "" });
  const add = useMutation({
    mutationFn: () => api<Member>("/members", { method: "POST", body: { ...form, password: form.password || null } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["members"] });
      onDone();
    },
  });

  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
      {add.error instanceof ApiError && <Alert>{add.error.message}</Alert>}
      <Field label="Nome">
        {(id) => <Input id={id} required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
      </Field>
      <Field label="E-mail">
        {(id) => <Input id={id} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
      </Field>
      <Field label="Perfil" hint={ROLE_HELP[form.role]}>
        {(id) => (
          <Select id={id} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            {roles.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </Select>
        )}
      </Field>
      <Field label="Senha inicial" hint="Mínimo de 8 caracteres. Se a pessoa já tem conta no AtendeJá, deixe em branco.">
        {(id) => <Input id={id} type="text" minLength={8} autoComplete="off" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />}
      </Field>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={add.isPending}>Adicionar</Button>
      </div>
    </form>
  );
}
