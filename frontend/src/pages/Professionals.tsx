import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { MANAGERS, useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { useProfessionals } from "@/api/hooks";
import type { Professional } from "@/api/types";
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
} from "@/components/ui";

export function ProfessionalsPage() {
  const { can } = useAuth();
  const isManager = can(...MANAGERS);
  const [showInactive, setShowInactive] = useState(false);
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = useProfessionals(showInactive);

  return (
    <>
      <PageHeader
        title="Profissionais"
        description="Quem atende, quais serviços faz e em quais horários."
        actions={
          isManager && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" /> Novo profissional
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
            title="Nenhum profissional cadastrado"
            description="Cadastre quem realiza os atendimentos. Depois defina os serviços e o expediente de cada um."
            action={isManager && <Button onClick={() => setCreating(true)}>Cadastrar profissional</Button>}
          />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.map((p) => (
              <li key={p.id}>
                <Link to={`/profissionais/${p.id}`} className="flex items-center gap-4 px-5 py-4 hover:bg-slate-50">
                  <span className="size-3 shrink-0 rounded-full" style={{ backgroundColor: p.color }} aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {p.name} {!p.active && <Badge>Desativado</Badge>}
                    </p>
                    <p className="truncate text-sm text-slate-500">
                      {p.specialty ? `${p.specialty} · ` : ""}
                      {p.services.length} serviço(s)
                    </p>
                  </div>
                  {p.working_hours.length === 0 && <Badge tone="warning">Sem expediente</Badge>}
                  <ChevronRight className="size-4 text-slate-400" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Sheet open={creating} title="Novo profissional" onClose={() => setCreating(false)}>
        {creating && <CreateProfessionalForm onDone={() => setCreating(false)} />}
      </Sheet>
    </>
  );
}

const COLORS = ["#6366f1", "#0d9488", "#db2777", "#ea580c", "#2563eb", "#7c3aed", "#65a30d", "#0891b2"];

function CreateProfessionalForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [color, setColor] = useState(COLORS[0]);

  const create = useMutation({
    mutationFn: () =>
      api<Professional>("/professionals", {
        method: "POST",
        body: { name, specialty: specialty || null, color },
      }),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["professionals"] });
      onDone();
      navigate(`/profissionais/${p.id}`);
    },
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      {create.error instanceof ApiError && <Alert>{create.error.message}</Alert>}
      <Field label="Nome">
        {(id) => <Input id={id} required minLength={2} value={name} onChange={(e) => setName(e.target.value)} />}
      </Field>
      <Field label="Especialidade" hint="Ex.: Esteticista, Fisioterapeuta.">
        {(id) => <Input id={id} value={specialty} onChange={(e) => setSpecialty(e.target.value)} />}
      </Field>
      <ColorPicker value={color} onChange={setColor} />
      <p className="text-sm text-slate-500">Depois de salvar, você define os serviços e o expediente.</p>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={create.isPending}>Salvar e continuar</Button>
      </div>
    </form>
  );
}

export function ColorPicker({ value, onChange }: { value: string; onChange: (c: string) => void }) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium text-slate-700">Cor na agenda</legend>
      <div className="flex flex-wrap gap-2">
        {COLORS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => onChange(c)}
            aria-label={`Cor ${c}`}
            aria-pressed={value === c}
            className="size-8 rounded-full ring-offset-2 aria-pressed:ring-2 aria-pressed:ring-slate-900"
            style={{ backgroundColor: c }}
          />
        ))}
      </div>
    </fieldset>
  );
}
