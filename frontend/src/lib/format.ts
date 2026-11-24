const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export const formatMoney = (cents: number) => brl.format(cents / 100);

/** "150,00" ou "150" ou "1.500,50" -> centavos. Devolve null se inválido. */
export function parseMoney(text: string): number | null {
  const clean = text.replace(/[R$\s.]/g, "").replace(",", ".");
  if (!clean) return null;
  const value = Number(clean);
  return Number.isFinite(value) && value >= 0 ? Math.round(value * 100) : null;
}

export const centsToInput = (cents: number) =>
  (cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 });

export function formatPhone(digits: string): string {
  const d = digits.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

export function formatDuration(min: number): string {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}h${String(m).padStart(2, "0")}` : `${h}h`;
}

export const hhmm = (time: string) => time.slice(0, 5);

const dateTime = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));

export function whatsappLink(phoneDigits: string, text?: string): string {
  const url = `https://wa.me/55${phoneDigits}`;
  return text ? `${url}?text=${encodeURIComponent(text)}` : url;
}

const dateOnly = new Intl.DateTimeFormat("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" });
export const formatDate = (iso: string) => dateOnly.format(new Date(iso));

const timeOnly = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });
export const formatTime = (iso: string) => timeOnly.format(new Date(iso));

/** Data local AAAA-MM-DD (sem converter para UTC). */
export const localDate = (d: Date) => d.toLocaleDateString("sv-SE");
/** Hora local HH:MM. */
export const localTime = (d: Date) => d.toTimeString().slice(0, 5);
