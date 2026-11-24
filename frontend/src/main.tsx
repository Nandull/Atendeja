import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "@/api/auth";
import { Spinner } from "@/components/ui";
import { Layout } from "@/components/Layout";
import { BlocksPage } from "@/pages/Blocks";
import { BookingPage } from "@/pages/Booking";
import { ClientsPage } from "@/pages/Clients";
import { HomePage } from "@/pages/Home";
import { LoginPage } from "@/pages/Login";
import { ProfessionalDetailPage } from "@/pages/ProfessionalDetail";
import { ProfessionalsPage } from "@/pages/Professionals";
import { ServicesPage } from "@/pages/Services";
import { SettingsPage } from "@/pages/Settings";
import { SignupPage } from "@/pages/Signup";
import { TeamPage } from "@/pages/Team";
import "./index.css";

// A agenda usa o FullCalendar (pesado). Carrega só quando abrir a tela, assim
// a página pública de agendamento fica leve no celular do cliente.
const AgendaPage = lazy(() => import("@/pages/Agenda").then((m) => ({ default: m.AgendaPage })));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function Private() {
  const { session, loading } = useAuth();
  if (loading) return <Spinner />;
  return session ? <Layout /> : <Navigate to="/entrar" replace />;
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return <Spinner />;
  return session ? <Navigate to="/" replace /> : children;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Painel: tudo que exige (ou oferece) login fica dentro do AuthProvider. */}
          <Route element={<AuthProvider><Outlet /></AuthProvider>}>
            <Route path="/entrar" element={<PublicOnly><LoginPage /></PublicOnly>} />
            <Route path="/cadastro" element={<PublicOnly><SignupPage /></PublicOnly>} />
            <Route element={<Private />}>
              <Route index element={<HomePage />} />
              <Route path="agenda" element={<Suspense fallback={<Spinner />}><AgendaPage /></Suspense>} />
              <Route path="clientes" element={<ClientsPage />} />
              <Route path="servicos" element={<ServicesPage />} />
              <Route path="profissionais" element={<ProfessionalsPage />} />
              <Route path="profissionais/:id" element={<ProfessionalDetailPage />} />
              <Route path="bloqueios" element={<BlocksPage />} />
              <Route path="equipe" element={<TeamPage />} />
              <Route path="configuracoes" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
          {/* Página pública do estabelecimento: /clinica-bella. Rotas fixas acima
              têm prioridade; por isso alguns nomes são reservados no cadastro. */}
          <Route path="/:slug" element={<BookingPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
