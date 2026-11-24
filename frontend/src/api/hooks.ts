import { useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { Member, Professional, Service } from "./types";

export const useServices = (includeInactive = false) =>
  useQuery({
    queryKey: ["services", { includeInactive }],
    queryFn: () => api<Service[]>("/services", { query: { include_inactive: includeInactive } }),
  });

export const useProfessionals = (includeInactive = false) =>
  useQuery({
    queryKey: ["professionals", { includeInactive }],
    queryFn: () =>
      api<Professional[]>("/professionals", { query: { include_inactive: includeInactive } }),
  });

export const useMembers = () =>
  useQuery({ queryKey: ["members"], queryFn: () => api<Member[]>("/members") });
