import { useMutation, useQuery } from "@tanstack/react-query";
import { UserPlus, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/api/client";
import type { Client, Page } from "@/api/types";
import { Alert, Button, Input } from "@/components/ui";
import { formatPhone } from "@/lib/format";

/** Busca cliente por nome/telefone ou cadastra na hora (fluxo comum na recepção). */
export function ClientPicker({
  value,
  onChange,
}: {
  value: Client | null;
  onChange: (c: Client | null) => void;
}) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [creating, setCreating] = useState(false);
  const [newClient, setNewClient] = useState({ name: "", phone: "" });

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  const results = useQuery({
    queryKey: ["clients", "picker", debounced],
    queryFn: () => api<Page<Client>>("/clients", { query: { q: debounced, limit: 6 } }),
    enabled: debounced.trim().length >= 2,
  });

  const create = useMutation({
    mutationFn: () => api<Client>("/clients", { method: "POST", body: newClient }),
    onSuccess: (c) => {
      onChange(c);
      setCreating(false);
    },
  });

  if (value) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-slate-300 bg-slate-50 px-3 py-2">
        <div>
          <p className="text-sm font-medium">{value.name}</p>
          <p className="text-xs text-slate-500">{formatPhone(value.phone)}</p>
        </div>
        <button type="button" onClick={() => onChange(null)} aria-label="Trocar cliente" className="rounded p-1 text-slate-500 hover:bg-slate-200">
          <X className="size-4" />
        </button>
      </div>
    );
  }

  if (creating) {
    return (
      <div className="space-y-2 rounded-lg border border-slate-200 p-3">
        {create.error instanceof ApiError && <Alert>{create.error.message}</Alert>}
        <Input aria-label="Nome do novo cliente" placeholder="Nome" value={newClient.name}
          onChange={(e) => setNewClient({ ...newClient, name: e.target.value })} />
        <Input aria-label="Telefone do novo cliente" placeholder="(21) 99999-0000" inputMode="tel" value={newClient.phone}
          onChange={(e) => setNewClient({ ...newClient, phone: formatPhone(e.target.value) })} />
        <div className="flex justify-end gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={() => setCreating(false)}>Voltar</Button>
          <Button type="button" size="sm" loading={create.isPending} onClick={() => create.mutate()}>Cadastrar cliente</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <Input aria-label="Buscar cliente" placeholder="Digite nome ou telefone" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
      {debounced.trim().length >= 2 && (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {results.data?.items.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => onChange(c)} className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-slate-50">
                <span className="font-medium">{c.name}</span>
                <span className="text-slate-500">{formatPhone(c.phone)}</span>
              </button>
            </li>
          ))}
          {results.data && !results.data.items.length && (
            <li className="px-3 py-2 text-sm text-slate-500">Nenhum cliente encontrado.</li>
          )}
        </ul>
      )}
      <button
        type="button"
        onClick={() => {
          const digits = q.replace(/\D/g, "");
          setNewClient(digits.length >= 8 ? { name: "", phone: formatPhone(digits) } : { name: q, phone: "" });
          setCreating(true);
        }}
        className="flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
      >
        <UserPlus className="size-4" /> Cadastrar novo cliente
      </button>
    </div>
  );
}
