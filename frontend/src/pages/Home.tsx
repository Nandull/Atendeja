import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "@/api/auth";
import { api } from "@/api/client";
import { useProfessionals, useServices } from "@/api/hooks";
import type { Client, Page } from "@/api/types";
import { Card, PageHeader, Spinner } from "@/components/ui";

export function HomePage() {
  const { session } = useAuth();
  const services = useServices();
  const pros = useProfessionals();
  const clients = useQuery({
    queryKey: ["clients", "count"],
    queryFn: () => api<Page<Client>>("/clients", { query: { limit: 1 } }),
  });

  if (services.isLoading || pros.isLoading || clients.isLoading) return <Spinner />;

  const nServices = services.data?.length ?? 0;
  const nPros = pros.data?.length ?? 0;
  const withHours = pros.data?.filter((p) => p.working_hours.length > 0).length ?? 0;
  const withServices = pros.data?.filter((p) => p.services.length > 0).length ?? 0;
  const nClients = clients.data?.total ?? 0;

  // Passos reais para deixar o estabelecimento pronto para receber agendamentos.
  const steps = [
    { done: nServices > 0, label: "Cadastrar os serviços oferecidos", to: "/servicos" },
    { done: nPros > 0, label: "Cadastrar os profissionais", to: "/profissionais" },
    { done: nPros > 0 && withServices === nPros, label: "Definir quais serviços cada profissional faz", to: "/profissionais" },
    { done: nPros > 0 && withHours === nPros, label: "Definir o expediente de cada profissional", to: "/profissionais" },
    { done: nClients > 0, label: "Cadastrar ou importar os clientes", to: "/clientes" },
  ];
  const done = steps.filter((s) => s.done).length;

  return (
    <>
      <PageHeader
        title={`Olá, ${session?.user.name.split(" ")[0]}`}
        description="Deixe o estabelecimento pronto para receber agendamentos."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: "Serviços ativos", value: nServices, to: "/servicos" },
          { label: "Profissionais ativos", value: nPros, to: "/profissionais" },
          { label: "Clientes cadastrados", value: nClients, to: "/clientes" },
        ].map((kpi) => (
          <Link key={kpi.label} to={kpi.to}>
            <Card className="p-5 transition-shadow hover:shadow-md">
              <p className="text-sm text-slate-500">{kpi.label}</p>
              <p className="mt-1 text-3xl font-semibold">{kpi.value}</p>
            </Card>
          </Link>
        ))}
      </div>

      <Card className="mt-6 p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Configuração inicial</h2>
          <span className="text-sm text-slate-500">{done} de {steps.length}</span>
        </div>
        <div className="mt-3 h-2 rounded-full bg-slate-100">
          <div className="h-2 rounded-full bg-brand-600 transition-all" style={{ width: `${(done / steps.length) * 100}%` }} />
        </div>
        <ul className="mt-4 divide-y divide-slate-100">
          {steps.map((s) => (
            <li key={s.label}>
              <Link to={s.to} className="flex items-center gap-3 py-3 text-sm hover:text-brand-700">
                {s.done ? (
                  <CheckCircle2 className="size-5 text-emerald-600" aria-label="Concluído" />
                ) : (
                  <Circle className="size-5 text-slate-300" aria-label="Pendente" />
                )}
                <span className={s.done ? "text-slate-500 line-through" : "font-medium"}>{s.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>

      <p className="mt-6 text-sm text-slate-500">
        Endereço reservado para o seu link de agendamento online:{" "}
        <span className="font-medium text-slate-700">atendeja.com.br/{session?.tenant.slug}</span>
      </p>
    </>
  );
}
