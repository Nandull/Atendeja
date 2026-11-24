import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import { NICHE_LABEL, type Session } from "@/api/types";
import { Alert, Button, Field, Input, Select } from "@/components/ui";
import { AuthShell } from "./AuthShell";

export function SignupPage() {
  const { setSession } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    business_name: "",
    niche: "estetica",
    owner_name: "",
    email: "",
    password: "",
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const signup = useMutation({
    mutationFn: () => api<Session>("/auth/signup", { method: "POST", body: form }),
    onSuccess: (s) => {
      setSession(s);
      navigate("/");
    },
  });

  return (
    <AuthShell title="Cadastre seu estabelecimento" subtitle="14 dias grátis. Leva menos de um minuto.">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          signup.mutate();
        }}
      >
        {signup.error instanceof ApiError && <Alert>{signup.error.message}</Alert>}
        <Field label="Nome do estabelecimento">
          {(id) => <Input id={id} required minLength={2} value={form.business_name} onChange={set("business_name")} placeholder="Clínica Bella Estética" />}
        </Field>
        <Field label="Tipo de negócio">
          {(id) => (
            <Select id={id} value={form.niche} onChange={set("niche")}>
              {Object.entries(NICHE_LABEL).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Seu nome">
          {(id) => <Input id={id} required minLength={2} autoComplete="name" value={form.owner_name} onChange={set("owner_name")} />}
        </Field>
        <Field label="E-mail">
          {(id) => <Input id={id} type="email" required autoComplete="email" value={form.email} onChange={set("email")} />}
        </Field>
        <Field label="Senha" hint="Mínimo de 8 caracteres.">
          {(id) => <Input id={id} type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set("password")} />}
        </Field>
        <Button type="submit" className="w-full" loading={signup.isPending}>
          Criar conta
        </Button>
        <p className="text-center text-sm text-slate-600">
          Já tem conta?{" "}
          <Link to="/entrar" className="font-medium text-brand-700 hover:underline">Entrar</Link>
        </p>
      </form>
    </AuthShell>
  );
}
