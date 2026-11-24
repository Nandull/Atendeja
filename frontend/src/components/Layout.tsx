import {
  CalendarOff,
  Home,
  LogOut,
  Menu,
  Scissors,
  Settings,
  UserRound,
  Users,
  UsersRound,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "@/api/auth";
import { ROLE_LABEL } from "@/api/types";
import { cn } from "@/lib/cn";

const NAV = [
  { to: "/", label: "Início", icon: Home, end: true },
  { to: "/clientes", label: "Clientes", icon: UsersRound },
  { to: "/servicos", label: "Serviços", icon: Scissors },
  { to: "/profissionais", label: "Profissionais", icon: UserRound },
  { to: "/bloqueios", label: "Bloqueios", icon: CalendarOff },
  { to: "/equipe", label: "Equipe e acessos", icon: Users },
  { to: "/configuracoes", label: "Estabelecimento", icon: Settings },
];

export function Layout() {
  const { session, logout } = useAuth();
  const [open, setOpen] = useState(false);
  if (!session) return null;

  const sidebar = (
    <nav className="flex h-full flex-col gap-1 p-3">
      <div className="mb-4 px-3 pt-2">
        <p className="text-lg font-bold text-brand-700">AtendeJá</p>
        <p className="truncate text-sm text-slate-600" title={session.tenant.name}>
          {session.tenant.name}
        </p>
      </div>
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium",
              isActive ? "bg-brand-50 text-brand-800" : "text-slate-700 hover:bg-slate-100",
            )
          }
        >
          <Icon className="size-4" aria-hidden />
          {label}
        </NavLink>
      ))}
      <div className="mt-auto border-t border-slate-200 px-3 pt-3">
        <p className="truncate text-sm font-medium">{session.user.name}</p>
        <p className="text-xs text-slate-500">{ROLE_LABEL[session.role]}</p>
        <button
          onClick={() => logout()}
          className="mt-2 flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900"
        >
          <LogOut className="size-4" aria-hidden /> Sair
        </button>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden w-60 shrink-0 border-r border-slate-200 bg-white md:block">
        <div className="sticky top-0 h-screen">{sidebar}</div>
      </aside>

      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
        <span className="font-bold text-brand-700">AtendeJá</span>
        <button onClick={() => setOpen(true)} aria-label="Abrir menu" className="p-1">
          <Menu className="size-5" />
        </button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} />
          <aside className="relative h-full w-64 bg-white">{sidebar}</aside>
        </div>
      )}

      <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-5xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
