export type Role = "owner" | "admin" | "receptionist" | "professional";

export interface User {
  id: string;
  name: string;
  email: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  niche: string;
  timezone: string;
  phone: string | null;
  address: string | null;
  plan: string;
  status: string;
}

export interface Session {
  user: User;
  tenant: Tenant;
  role: Role;
  tenants: { slug: string; name: string; role: Role }[];
}

export interface Member {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: Role;
}

export interface Service {
  id: string;
  name: string;
  description: string | null;
  duration_min: number;
  buffer_min: number;
  price_cents: number;
  online_booking: boolean;
  active: boolean;
}

export interface WorkingHour {
  weekday: number;
  start_time: string;
  end_time: string;
}

export interface ProfessionalService {
  service_id: string;
  name: string;
  duration_min: number;
  price_cents: number;
  price_cents_override: number | null;
}

export interface Professional {
  id: string;
  name: string;
  specialty: string | null;
  color: string;
  user_id: string | null;
  active: boolean;
  services: ProfessionalService[];
  working_hours: WorkingHour[];
}

export interface TimeBlock {
  id: string;
  professional_id: string | null;
  starts_at: string;
  ends_at: string;
  reason: string | null;
}

export interface Client {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  birth_date: string | null;
  notes: string | null;
  source: string | null;
  marketing_consent: boolean;
  active: boolean;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export const ROLE_LABEL: Record<Role, string> = {
  owner: "Dono",
  admin: "Gerente",
  receptionist: "Recepção",
  professional: "Profissional",
};

export const NICHE_LABEL: Record<string, string> = {
  estetica: "Clínica de estética",
  fisioterapia: "Fisioterapia",
  nutricao: "Nutrição",
  podologia: "Podologia",
  salao: "Salão de beleza",
  barbearia: "Barbearia",
  outro: "Outro",
};

export const WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];
