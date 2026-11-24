import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "@/api/auth";
import { api, ApiError } from "@/api/client";
import type { Session } from "@/api/types";
import { Alert, Button, Field, Input, Select } from "@/components/ui";
import { AuthShell } from "./AuthShell";

type Choice = { slug: string; name: string };

export function LoginPage() {
  const { setSession } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [choices, setChoices] = useState<Choice[] | null>(null);
  const [tenantSlug, setTenantSlug] = useState("");

  const login = useMutation({
    mutationFn: () =>
      api<Session>("/auth/login", {
        method: "POST",
        body: { email, password, tenant_slug: tenantSlug || undefined },
      }),
    onSuccess: (s) => {
      setSession(s);
      navigate("/");
    },
    onError: (e) => {
      // Pessoa que trabalha em mais de um estabelecimento: pede para escolher.
      if (e instanceof ApiError && e.status === 409) {
        const list = (e.detail as { tenants: Choice[] }).tenants;
        setChoices(list);
        setTenantSlug(list[0]?.slug ?? "");
      }
    },
  });

  const error = login.error instanceof ApiError && login.error.status !== 409 ? login.error.message : null;

  return (
    <AuthShell title="Entrar" subtitle="Acesse a agenda do seu estabelecimento.">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        {error && <Alert>{error}</Alert>}
        <Field label="E-mail">
          {(id) => (
            <Input id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          )}
        </Field>
        <Field label="Senha">
          {(id) => (
            <Input id={id} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          )}
        </Field>
        {choices && (
          <Field label="Estabelecimento" hint="Você tem acesso a mais de um.">
            {(id) => (
              <Select id={id} value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)}>
                {choices.map((c) => (
                  <option key={c.slug} value={c.slug}>{c.name}</option>
                ))}
              </Select>
            )}
          </Field>
        )}
        <Button type="submit" className="w-full" loading={login.isPending}>
          Entrar
        </Button>
        <p className="text-center text-sm text-slate-600">
          Ainda não tem conta?{" "}
          <Link to="/cadastro" className="font-medium text-brand-700 hover:underline">
            Cadastre seu estabelecimento
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
