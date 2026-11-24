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
  booking_enabled: boolean;
  booking_min_notice_min: number;
  booking_window_days: number;
  booking_note: string | null;
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

export type AppointmentStatus = "scheduled" | "confirmed" | "completed" | "canceled" | "no_show";

export interface Appointment {
  id: string;
  client: { id: string; name: string; phone: string };
  professional: { id: string; name: string; color: string };
  service: { id: string; name: string };
  starts_at: string;
  ends_at: string;
  blocked_until: string;
  status: AppointmentStatus;
  price_cents: number;
  origin: string;
  notes: string | null;
  cancel_reason: string | null;
  created_at: string;
}

export interface Slots {
  date: string;
  professional_id: string;
  service_id: string;
  duration_min: number;
  price_cents: number;
  slots: string[];
}

export interface ClientHistory {
  stats: {
    completed: number;
    no_show: number;
    canceled: number;
    upcoming: number;
    total_spent_cents: number;
    first_visit: string | null;
    last_visit: string | null;
    avg_days_between_visits: number | null;
  };
  appointments: Appointment[];
}

export const STATUS_LABEL: Record<AppointmentStatus, string> = {
  scheduled: "Agendado",
  confirmed: "Confirmado",
  completed: "Atendido",
  canceled: "Cancelado",
  no_show: "Faltou",
};

// ---- Página pública de agendamento ----
export interface PublicProfessional {
  id: string;
  name: string;
  specialty: string | null;
  color: string;
  price_cents: number;
}

export interface PublicService {
  id: string;
  name: string;
  description: string | null;
  duration_min: number;
  price_cents: number;
  price_varies: boolean;
  professionals: PublicProfessional[];
}

export interface PublicBusiness {
  name: string;
  slug: string;
  niche: string;
  phone: string | null;
  address: string | null;
  timezone: string;
  note: string | null;
  min_notice_min: number;
  window_days: number;
  services: PublicService[];
}

export interface PublicDay {
  date: string;
  slots: { starts_at: string; professional_id: string }[];
}

export interface PublicAvailability {
  service_id: string;
  professional_id: string | null;
  days: PublicDay[];
}

export interface PublicBooking {
  id: string;
  starts_at: string;
  ends_at: string;
  service: string;
  professional: string;
  price_cents: number;
  business_name: string;
  business_phone: string | null;
  business_address: string | null;
  timezone: string;
}
