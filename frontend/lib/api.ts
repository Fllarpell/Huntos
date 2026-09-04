import type {
  CalendarBoard,
  CollisionOut,
  CustomFieldDef,
  HuntContact,
  HuntDesk,
  HuntList,
  NudgeOut,
  PingSlot,
  PipelineStage,
  Profile,
  ScraperConfig,
  ScraperRun,
  DonorCrawl,
  Thesis,
  Vacancy,
  WavePack,
  CareerBoard,
  InternshipKind,
  InternshipRow,
  InternshipTrackStatus,
  HackathonRow,
  HackathonTrackStatus,
  SalaryMarket,
} from "./types";

export type VacancyEventDraft = {
  kind: "screening" | "interview" | "assignment" | "offer_deadline";
  starts_at: string;
  ends_at?: string | null;
  label?: string | null;
};

export type VacancyDraft = {
  title?: string;
  company?: string | null;
  company_inn?: string | null;
  grade?: string | null;
  work_format?: string | null;
  location?: string | null;
  language?: string | null;
  salary_raw?: string | null;
  description?: string | null;
  source_url?: string | null;
  telegram_alias?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  notes?: string | null;
  skills?: string[];
  custom_values?: Record<string, string>;
  card_fields?: CustomFieldDef[];
  hunt_id?: number | null;
  pipeline_stage?: PipelineStage;
  next_step_at?: string | null;
  next_step_kind?: "screening" | "interview" | "assignment" | "offer_deadline" | null;
};

export type AuthUser = {
  id: number;
  email: string;
  is_host?: boolean;
  can_observe?: boolean;
};

export type ChatThread = {
  id: number;
  peer_id: number;
  peer_name: string;
  online: boolean;
  last_seen_at: string | null;
  last_body: string | null;
  last_at: string | null;
  unread: number;
};

export type ChatMessage = {
  id: number;
  sender_id: number;
  mine: boolean;
  body: string;
  created_at: string;
};

export type TelegramHost = {
  connected: boolean;
  status: string;
  phone: string | null;
  username: string | null;
  display_name: string | null;
  error: string | null;
  connected_at: string | null;
  api_id_set: boolean;
  waiting_code: boolean;
  needs_password: boolean;
};

export type TelegramChannel = {
  id: number;
  username: string;
  title: string | null;
  enabled: boolean;
  joined: boolean;
  status: string;
  error: string | null;
  last_parsed_at: string | null;
  added_url: string | null;
  added_by_user_id: number | null;
};

export type TelegramParseRun = {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  found_count: number;
  new_count: number;
  error: string | null;
};

export type TelegramPool = {
  host: TelegramHost;
  channels: TelegramChannel[];
  last_run: TelegramParseRun | null;
};

// Browser must hit the same origin as the page. Next rewrites /api → :8000, so
// hunt_session is a first-party cookie. NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
// makes Chrome treat the cookie as third-party: login 200, then /me 401.
const API = typeof window === "undefined" ? (process.env.NEXT_PUBLIC_API_URL ?? "") : "";

let asUserId: number | null = null;

export function setAsUser(id: number | null) {
  asUserId = id;
}

export function getAsUser() {
  return asUserId;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  opts?: { authRedirect?: boolean; asUser?: boolean },
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  };
  if (opts?.asUser !== false && asUserId != null) {
    headers["X-Hunt-As"] = String(asUserId);
  }
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (res.status === 401 && (opts?.authRedirect ?? true) && typeof window !== "undefined") {
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new Error("Нужно войти");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = (await res.json()) as { detail?: string };
      if (data.detail) detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ ok: boolean }>("/api/health", undefined, { authRedirect: false }),
  me: () => request<AuthUser>("/api/auth/me", undefined, { authRedirect: false, asUser: false }),
  users: () => request<AuthUser[]>("/api/auth/users", undefined, { asUser: false }),
  patchUser: (id: number, can_observe: boolean) =>
    request<AuthUser>(`/api/auth/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ can_observe }),
    }, { asUser: false }),
  googleAvailable: () =>
    request<{ available: boolean }>("/api/auth/google", undefined, { authRedirect: false, asUser: false }),
  googleLogin: () =>
    request<{ url: string }>("/api/auth/google", { method: "POST" }, { authRedirect: false, asUser: false }),
  register: (email: string, password: string) =>
    request<AuthUser>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }, { authRedirect: false, asUser: false }),
  login: (email: string, password: string) =>
    request<AuthUser>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }, { authRedirect: false, asUser: false }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }, { authRedirect: false, asUser: false }),
  telegramBot: () =>
    request<{
      available: boolean;
      username: string | null;
      connected: boolean;
      paused: boolean;
      telegram_username: string | null;
      want_vacancies: boolean;
      want_internships: boolean;
      want_hackathons: boolean;
      want_steps: boolean;
      want_ping: boolean;
    }>("/api/telegram/bot", undefined, { asUser: false }),
  telegramBotLink: () => request<{ url: string; username: string }>("/api/telegram/bot/link", { method: "POST" }, { asUser: false }),
  telegramBotUnlink: () =>
    request<{
      available: boolean;
      username: string | null;
      connected: boolean;
      paused: boolean;
      telegram_username: string | null;
      want_vacancies: boolean;
      want_internships: boolean;
      want_hackathons: boolean;
      want_steps: boolean;
      want_ping: boolean;
    }>("/api/telegram/bot/unlink", { method: "POST" }, { asUser: false }),
  saveTelegramBotPrefs: (payload: Record<string, boolean>) =>
    request<{
      available: boolean;
      connected: boolean;
      want_vacancies: boolean;
      want_internships: boolean;
      want_hackathons: boolean;
      want_steps: boolean;
      want_ping: boolean;
      paused: boolean;
      telegram_username: string | null;
      username: string | null;
    }>("/api/telegram/bot/prefs", { method: "PUT", body: JSON.stringify(payload) }, { asUser: false }),
  saveTelegramBotToken: (token: string) =>
    request<{ available: boolean; username: string | null }>(
      "/api/telegram/bot/token",
      { method: "PUT", body: JSON.stringify({ token }) },
      { asUser: false },
    ),
  sendFeedback: (payload: {
    kind: "bug" | "idea";
    body: string;
    page?: string;
    contact_name?: string;
    reply_to?: string;
  }) =>
    request<{ ok: boolean }>("/api/feedback", { method: "POST", body: JSON.stringify(payload) }, { asUser: false }),
  feedback: () =>
    request<
      {
        id: number;
        kind: string;
        body: string;
        page: string | null;
        contact_name: string | null;
        reply_to: string | null;
        email: string;
        created_at: string;
      }[]
    >("/api/feedback", undefined, { asUser: false }),
  chatInbox: () =>
    request<{
      host: boolean;
      unread_total: number;
      admin: { online: boolean; last_seen_at: string | null; name: string };
      threads: ChatThread[];
    }>("/api/chat/inbox", undefined, { asUser: false }),
  chatOpen: (userId?: number) =>
    request<ChatThread>("/api/chat/open", {
      method: "POST",
      body: JSON.stringify(userId != null ? { user_id: userId } : {}),
    }, { asUser: false }),
  chatMessages: (conversationId: number, after = 0) =>
    request<ChatMessage[]>(
      `/api/chat/${conversationId}/messages${after ? `?after=${after}` : ""}`,
      undefined,
      { asUser: false },
    ),
  chatSend: (conversationId: number, body: string) =>
    request<ChatMessage>(
      `/api/chat/${conversationId}/messages`,
      { method: "POST", body: JSON.stringify({ body }) },
      { asUser: false },
    ),
  vacancies: (
    params: {
      stage?: PipelineStage;
      q?: string;
      sort?: string;
      grade?: string[];
      format?: string[];
      nda?: string;
      salary?: string;
      source?: string[];
      exclude_company?: string[];
      stack?: string[];
      search_id?: number[];
      hunt_id?: number | null;
      limit?: number;
    } = {},
  ) => {
    const sp = new URLSearchParams();
    if (params.stage) sp.set("stage", params.stage);
    if (params.q) sp.set("q", params.q);
    if (params.sort) sp.set("sort", params.sort);
    if (params.nda && params.nda !== "any") sp.set("nda", params.nda);
    if (params.salary && params.salary !== "any") sp.set("salary", params.salary);
    if (params.hunt_id) sp.set("hunt_id", String(params.hunt_id));
    if (params.limit) sp.set("limit", String(params.limit));
    for (const g of params.grade ?? []) sp.append("grade", g);
    for (const f of params.format ?? []) sp.append("format", f);
    for (const s of params.source ?? []) sp.append("source", s);
    for (const name of params.exclude_company ?? []) sp.append("exclude_company", name);
    for (const item of params.stack ?? []) sp.append("stack", item);
    for (const id of params.search_id ?? []) sp.append("search_id", String(id));
    return request<{ items: Vacancy[]; total: number }>(`/api/vacancies?${sp.toString()}`);
  },
  vacancy: (id: number) => request<Vacancy>(`/api/vacancies/${id}`),
  addEvent: (vacancyId: number, payload: VacancyEventDraft) =>
    request<Vacancy>(`/api/vacancies/${vacancyId}/events`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patchEvent: (eventId: number, payload: Partial<VacancyEventDraft>) =>
    request<Vacancy>(`/api/events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteEvent: (eventId: number) => request<Vacancy>(`/api/events/${eventId}`, { method: "DELETE" }),
  createVacancy: (payload: VacancyDraft = {}) =>
    request<Vacancy>("/api/vacancies", { method: "POST", body: JSON.stringify(payload) }),
  patchVacancy: (id: number, payload: VacancyDraft) =>
    request<Vacancy>(`/api/vacancies/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  setStage: (id: number, stage: PipelineStage, position?: number, huntId?: number | null) =>
    request<Vacancy>(`/api/vacancies/${id}/stage`, {
      method: "PATCH",
      body: JSON.stringify({ stage, position, hunt_id: huntId ?? undefined }),
    }),
  saveNotes: (id: number, notes: string) =>
    request<Vacancy>(`/api/vacancies/${id}/notes`, {
      method: "PATCH",
      body: JSON.stringify({ notes }),
    }),
  saveTelegram: (id: number, telegram_alias: string) =>
    request<Vacancy>(`/api/vacancies/${id}/telegram`, {
      method: "PATCH",
      body: JSON.stringify({ telegram_alias }),
    }),
  score: (id: number) => request<Vacancy>(`/api/vacancies/${id}/score`, { method: "POST" }),
  adapt: (id: number) => request<NonNullable<Vacancy["adaptation_advice"]>>(`/api/vacancies/${id}/adapt`, { method: "POST" }),
  coverLetter: (id: number) =>
    request<{ cover_letter: string }>(`/api/vacancies/${id}/cover-letter`, { method: "POST" }),
  bulkStage: (ids: number[], stage: PipelineStage, huntId?: number | null) =>
    request<{ ok: boolean; moved: number }>("/api/vacancies/bulk-stage", {
      method: "POST",
      body: JSON.stringify({ ids, stage, hunt_id: huntId ?? undefined }),
    }),
  pipeline: (huntId?: number | null) =>
    request<{ stage: PipelineStage; items: Vacancy[] }[]>(
      `/api/pipeline${huntId ? `?hunt_id=${huntId}` : ""}`,
    ),
  reorder: (items: { id: number; stage: PipelineStage; position: number }[]) =>
    request<{ ok: boolean }>("/api/pipeline/reorder", {
      method: "POST",
      body: JSON.stringify(items),
    }),
  profile: () => request<Profile>("/api/settings/profile"),
  ownProfile: () => request<Profile>("/api/settings/profile", undefined, { asUser: false }),
  saveProfile: (
    payload: Partial<Profile> & {
      openai_api_key?: string;
      resume_text?: string;
      google_client_id?: string;
      google_client_secret?: string;
    },
    opts?: { asUser?: boolean },
  ) =>
    request<Profile>("/api/settings/profile", { method: "PUT", body: JSON.stringify(payload) }, opts),
  uploadResume: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Profile>("/api/settings/profile/resume", { method: "POST", body });
  },
  configs: () => request<ScraperConfig[]>("/api/scraper-configs"),
  saveConfig: (payload: Partial<ScraperConfig> & { name: string }, id?: number) =>
    id
      ? request<ScraperConfig>(`/api/scraper-configs/${id}`, { method: "PUT", body: JSON.stringify(payload) })
      : request<ScraperConfig>("/api/scraper-configs", { method: "POST", body: JSON.stringify(payload) }),
  deleteConfig: (id: number) => request<{ ok: boolean }>(`/api/scraper-configs/${id}`, { method: "DELETE" }),
  runScraper: (id: number) => request<{ ok: boolean; status?: string }>(`/api/scraper/run/${id}`, { method: "POST" }),
  crawls: () => request<DonorCrawl[]>("/api/scraper/crawls", undefined, { asUser: false }),
  boards: () => request<CareerBoard[]>("/api/scraper/boards"),
  runs: () => request<ScraperRun[]>("/api/scraper/runs"),
  scorePending: () => request<{ scored: number }>("/api/scraper/score-pending", { method: "POST" }),
  telegramPool: () => request<TelegramPool>("/api/telegram/pool", undefined, { asUser: false }),
  telegramHostStart: (payload: { phone: string; api_id?: number; api_hash?: string }) =>
    request<TelegramHost>("/api/telegram/host/start", { method: "POST", body: JSON.stringify(payload) }, { asUser: false }),
  telegramHostConfirm: (payload: { code?: string; password?: string }) =>
    request<TelegramHost>("/api/telegram/host/confirm", { method: "POST", body: JSON.stringify(payload) }, { asUser: false }),
  telegramHostDisconnect: () => request<TelegramHost>("/api/telegram/host/disconnect", { method: "POST" }, { asUser: false }),
  addTelegramChannel: (url: string) =>
    request<TelegramChannel>("/api/telegram/channels", { method: "POST", body: JSON.stringify({ url }) }, { asUser: false }),
  deleteTelegramChannel: (id: number) =>
    request<{ ok: boolean }>(`/api/telegram/channels/${id}`, { method: "DELETE" }, { asUser: false }),
  parseTelegram: () =>
    request<{ ok: boolean; status: string }>("/api/telegram/parse", { method: "POST" }, { asUser: false }),
  joinTelegramPool: () =>
    request<{ ok: boolean; new_count: number }>("/api/telegram/join", { method: "POST" }, { asUser: false }),
  telegramDraft: (id: number) =>
    request<{ telegram_message: string }>(`/api/vacancies/${id}/telegram-draft`, { method: "POST" }),
  markWrote: (id: number) => request<Vacancy>(`/api/vacancies/${id}/wrote`, { method: "POST" }),
  markPinged: (id: number) => request<Vacancy>(`/api/vacancies/${id}/pinged`, { method: "POST" }),
  markHhPulse: (id: number, pulse: "invited" | "discarded" | null) =>
    request<Vacancy>(`/api/vacancies/${id}/hh-pulse`, {
      method: "POST",
      body: JSON.stringify({ pulse }),
    }),
  googleConnect: () => request<{ url: string }>("/api/google/connect", { method: "POST" }, { asUser: false }),
  googleDisconnect: () =>
    request<{ connected: boolean; email: string | null }>("/api/google/disconnect", { method: "POST" }, { asUser: false }),
  googleCalendar: () =>
    request<{ connected: boolean; calendar_ready?: boolean; calendar_error?: string | null }>(
      "/api/google/calendar",
      { method: "POST" },
      { asUser: false },
    ),
  collisions: () => request<CollisionOut>("/api/calendar/collisions"),
  calendar: () => request<CalendarBoard>("/api/calendar"),
  nudge: (huntId?: number | null) =>
    request<NudgeOut>(`/api/nudge${huntId ? `?hunt_id=${huntId}` : ""}`),
  nudgePinged: (ids: number[]) =>
    request<{ ok: boolean; pinged: number; total: number }>("/api/nudge/pinged", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  nudgeSlot: (payload: { thesis_id: number | null; ping_at: string | null }) =>
    request<PingSlot>("/api/nudge/slot", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  theses: () => request<Thesis[]>("/api/theses"),
  hunts: () => request<HuntList>("/api/hunts"),
  setActiveHunt: (hunt_id: number | null) =>
    request<HuntList>("/api/hunts/active", {
      method: "PATCH",
      body: JSON.stringify({ hunt_id }),
    }),
  saveHuntFields: (thesisId: number, custom_fields: CustomFieldDef[]) =>
    request<Thesis>(`/api/theses/${thesisId}/fields`, {
      method: "PUT",
      body: JSON.stringify({ custom_fields }),
    }),
  setVacancyHunts: (id: number, hunt_ids: number[]) =>
    request<Vacancy>(`/api/vacancies/${id}/hunts`, {
      method: "PUT",
      body: JSON.stringify({ hunt_ids }),
    }),
  huntDesk: () => request<HuntDesk>("/api/hunt/desk"),
  contacts: (q?: string, pool?: "all") => {
    const sp = new URLSearchParams();
    if (q) sp.set("q", q);
    if (pool) sp.set("pool", pool);
    const qs = sp.toString();
    return request<HuntContact[]>(`/api/contacts${qs ? `?${qs}` : ""}`);
  },
  saveContact: (payload: {
    company?: string | null;
    company_inn?: string | null;
    telegram_alias?: string | null;
    contact_email?: string | null;
    contact_phone?: string | null;
  }) =>
    request<HuntContact>("/api/contacts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteSavedContact: (id: number) =>
    request<{ ok: boolean }>(`/api/contacts/saved/${id}`, { method: "DELETE" }),
  internships: (kind?: InternshipKind) => {
    const qs = kind ? `?kind=${encodeURIComponent(kind)}` : "";
    return request<InternshipRow[]>(`/api/internships${qs}`);
  },
  saveInternshipTrack: (
    slug: string,
    payload: { status?: InternshipTrackStatus | null; notes?: string | null; applied_at?: string | null },
  ) =>
    request<InternshipRow>(`/api/internships/${encodeURIComponent(slug)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  hackathons: (params?: { status?: string; registration?: string; source?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.registration) qs.set("registration", params.registration);
    if (params?.source) qs.set("source", params.source);
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<HackathonRow[]>(`/api/hackathons${suffix}`);
  },
  syncHackathons: () => request<{ created: number; updated: number; errors: number; total: number }>("/api/hackathons/sync", { method: "POST" }),
  saveHackathonTrack: (
    id: number,
    payload: { status?: HackathonTrackStatus | null; notes?: string | null; applied_at?: string | null },
  ) =>
    request<HackathonRow>(`/api/hackathons/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  saveThesis: (payload: Partial<Thesis> & { name: string }, id?: number) =>
    id
      ? request<Thesis>(`/api/theses/${id}`, { method: "PUT", body: JSON.stringify(payload) })
      : request<Thesis>("/api/theses", { method: "POST", body: JSON.stringify(payload) }),
  deleteThesis: (id: number) => request<{ ok: boolean }>(`/api/theses/${id}`, { method: "DELETE" }),
  salaryMarket: (params?: { hunt_id?: number; grade?: string; specialty?: string; refresh?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.hunt_id) qs.set("hunt_id", String(params.hunt_id));
    if (params?.grade) qs.set("grade", params.grade);
    if (params?.specialty) qs.set("specialty", params.specialty);
    if (params?.refresh) qs.set("refresh", "1");
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<SalaryMarket>(`/api/salary-market${suffix}`);
  },
  refreshLevelsFyi: () => request<{ count: number; errors: number }>("/api/salary-market/levels/refresh", { method: "POST" }),
  wavePack: (thesisId: number) => request<WavePack>(`/api/theses/${thesisId}/wave-pack`),
  waveWrote: (thesisId: number, ids: number[]) =>
    request<{ ok: boolean; wrote: number; wave: Thesis["last_wave"] }>(`/api/theses/${thesisId}/wave/wrote`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
};
