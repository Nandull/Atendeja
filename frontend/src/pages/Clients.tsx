import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircle, Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/api/client";
import type { Client, Page } from "@/api/types";
import {
  Alert,
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
import { ClientHistory } from "@/components/ClientHistory";
import { formatPhone, whatsappLink } from "@/lib/format";

const PAGE_SIZE = 25;

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function ClientsPage() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<Client | "new" | null>(null);
  const search = useDebounced(q);

  useEffect(() => setPage(0), [search]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["clients", search, page],
    queryFn: () =>
      api<Page<Client>>("/clients", { query: { q: search, limit: PAGE_SIZE, offset: page * PAGE_SIZE } }),
    placeholderData: keepPreviousData,
  });
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <PageHeader
        title="Clientes"
        description={data ? `${data.total} cliente(s)${search ? " encontrados" : " cadastrados"}` : undefined}
        actions={
          <Button onClick={() => setEditing("new")}>
            <Plus className="size-4" /> Novo cliente
          </Button>
        }
      />
      <div className="relative mb-3 max-w-md">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
        <Input aria-label="Buscar clientes" className="pl-9" placeholder="Buscar por nome ou telefone" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Card>
        {isLoading ? (
          <Spinner />
        ) : !data?.items.length ? (
          search ? (
            <EmptyState title="Nenhum cliente encontrado" description={`Nada com "${search}".`} />
          ) : (
            <EmptyState
              title="Nenhum cliente cadastrado"
              description="Os clientes que agendarem online entram aqui automaticamente. Você também pode cadastrar manualmente."
              action={<Button onClick={() => setEditing("new")}>Cadastrar cliente</Button>}
            />
          )
        ) : (
          <div className={isFetching ? "opacity-60" : undefined}>
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 text-left text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Nome</th>
                  <th className="px-5 py-3 font-medium">Telefone</th>
                  <th className="hidden px-5 py-3 font-medium sm:table-cell">E-mail</th>
                  <th className="w-12 px-5 py-3"><span className="sr-only">WhatsApp</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((c) => (
                  <tr key={c.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setEditing(c)}>
                    <td className="px-5 py-3 font-medium">{c.name}</td>
                    <td className="px-5 py-3 whitespace-nowrap">{formatPhone(c.phone)}</td>
                    <td className="hidden truncate px-5 py-3 text-slate-500 sm:table-cell">{c.email}</td>
                    <td className="px-5 py-3">
                      <a href={whatsappLink(c.phone)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
                        aria-label={`WhatsApp de ${c.name}`} className="text-emerald-600 hover:text-emerald-700">
                        <MessageCircle className="size-4" />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {pages > 1 && (
              <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3 text-sm">
                <span className="text-slate-500">Página {page + 1} de {pages}</span>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</Button>
                  <Button size="sm" variant="secondary" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Próxima</Button>
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
      <Sheet open={editing !== null} title={editing === "new" ? "Novo cliente" : "Cliente"} onClose={() => setEditing(null)}>
        {editing !== null && (
          <ClientForm
            key={editing === "new" ? "new" : editing.id}
            client={editing === "new" ? null : editing}
            onDone={() => setEditing(null)}
            onOpenExisting={(c) => setEditing(c)}
          />
        )}
      </Sheet>
    </>
  );
}

function ClientForm({
  client,
  onDone,
  onOpenExisting,
}: {
  client: Client | null;
  onDone: () => void;
  onOpenExisting: (c: Client) => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: client?.name ?? "",
    phone: client ? formatPhone(client.phone) : "",
    email: client?.email ?? "",
    birth_date: client?.birth_date ?? "",
    source: client?.source ?? "",
    notes: client?.notes ?? "",
    marketing_consent: client?.marketing_consent ?? false,
    active: client?.active ?? true,
  });

  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...form,
        email: form.email || null,
        birth_date: form.birth_date || null,
        source: form.source || null,
        notes: form.notes || null,
      };
      return client
        ? api<Client>(`/clients/${client.id}`, { method: "PATCH", body })
        : api<Client>("/clients", { method: "POST", body: { ...body, active: undefined } });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      onDone();
    },
  });

  // Telefone já cadastrado: a API devolve qual cliente é, para abrir o cadastro dele.
  const dup =
    save.error instanceof ApiError && save.error.status === 409
      ? (save.error.detail as { client_id?: string; name?: string })
      : null;

  async function openExisting() {
    if (!dup?.client_id) return;
    onOpenExisting(await api<Client>(`/clients/${dup.client_id}`));
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      {save.error instanceof ApiError && (
        <Alert>
          {save.error.message}
          {dup?.client_id && dup.client_id !== client?.id && (
            <button type="button" onClick={openExisting} className="ml-1 font-medium underline">
              Abrir cadastro de {dup.name}
            </button>
          )}
        </Alert>
      )}
      <Field label="Nome">
        {(id) => <Input id={id} required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
      </Field>
      <Field label="Telefone (WhatsApp)">
        {(id) => <Input id={id} required inputMode="tel" placeholder="(21) 99999-0000" value={form.phone}
          onChange={(e) => setForm({ ...form, phone: formatPhone(e.target.value) })} />}
      </Field>
      <Field label="E-mail">
        {(id) => <Input id={id} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Nascimento">
          {(id) => <Input id={id} type="date" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} />}
        </Field>
        <Field label="Como conheceu">
          {(id) => <Input id={id} placeholder="Instagram, indicação..." maxLength={40} value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} />}
        </Field>
      </div>
      <Field label="Observações e preferências" hint="Evite registrar dados de saúde aqui.">
        {(id) => <Textarea id={id} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />}
      </Field>
      <Checkbox
        label="Aceita receber promoções"
        description="Consentimento para mensagens de marketing (LGPD)."
        checked={form.marketing_consent}
        onChange={(v) => setForm({ ...form, marketing_consent: v })}
      />
      {client && <Checkbox label="Cliente ativo" checked={form.active} onChange={(v) => setForm({ ...form, active: v })} />}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={save.isPending}>Salvar</Button>
      </div>
      {client && (
        <section className="border-t border-slate-200 pt-4">
          <h3 className="mb-3 font-semibold">Histórico</h3>
          <ClientHistory clientId={client.id} />
        </section>
      )}
    </form>
  );
}
