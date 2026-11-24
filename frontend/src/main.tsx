import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "@/api/auth";
import { Spinner } from "@/components/ui";
import { Layout } from "@/components/Layout";
import { BlocksPage } from "@/pages/Blocks";
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
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/entrar" element={<PublicOnly><LoginPage /></PublicOnly>} />
            <Route path="/cadastro" element={<PublicOnly><SignupPage /></PublicOnly>} />
            <Route element={<Private />}>
              <Route index element={<HomePage />} />
              <Route path="clientes" element={<ClientsPage />} />
              <Route path="servicos" element={<ServicesPage />} />
              <Route path="profissionais" element={<ProfessionalsPage />} />
              <Route path="profissionais/:id" element={<ProfessionalDetailPage />} />
              <Route path="bloqueios" element={<BlocksPage />} />
              <Route path="equipe" element={<TeamPage />} />
              <Route path="configuracoes" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
