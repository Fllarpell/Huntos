export type PipelineStage =
  | "inbox"
  | "to_apply"
  | "waiting"
  | "screening"
  | "interview"
  | "offer"
  | "rejected"
  | "trash";

export type ScoringStatus = "pending" | "scored" | "error" | "skipped";

export type VacancyEventItem = {
  id: number;
  vacancy_id: number;
  kind: "screening" | "interview" | "offer_deadline";
  starts_at: string;
  ends_at?: string | null;
  label: string | null;
  display_label: string;
  google_event_id?: string | null;
  google_sync_error?: string | null;
  calendar_connected?: boolean;
};

export type Vacancy = {
  id: number;
  source: string;
  source_id: string;
  source_url: string | null;
  title: string;
  company: string | null;
  company_inn?: string | null;
  company_icon: string | null;
  grade: string | null;
  work_format: string | null;
  category: string | null;
  salary_raw: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  description: string | null;
  requirements: string | null;
  tasks_html: string | null;
  conditions_html: string | null;
  important_info: string | null;
  skills: string[];
  tags: string[];
  published_at: string | null;
  pipeline_stage: PipelineStage;
  pipeline_position: number;
  match_score: number | null;
  scoring_status: ScoringStatus;
  match_rationale: {
    summary?: string;
    verdict?: string;
    strengths?: string[];
    gaps?: string[];
    must_have_missing?: string[];
    highlight_skills?: string[];
  } | null;
  adaptation_advice: {
    missing_skills?: string[];
    suggestions?: { section: string; change: string; why: string }[];
    do_not_invent?: string[];
  } | null;
  cover_letter: string | null;
  notes: string | null;
  telegram_alias: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  telegram_url: string | null;
  telegram_message: string | null;
  extra_sources: { source?: string; source_id?: string; source_url?: string }[];
  last_touch_at: string | null;
  outreach_at: string | null;
  pinged_at?: string | null;
  hh_pulse?: "invited" | "discarded" | null;
  hh_pulse_at?: string | null;
  next_step_at?: string | null;
  next_step_kind?: "screening" | "interview" | "offer_deadline" | null;
  google_event_id?: string | null;
  google_sync_error?: string | null;
  calendar_connected?: boolean;
  collision_hint?: string | null;
  collision_peers?: number;
  ping_due?: boolean;
  silence_days?: number | null;
  stage_entered_at?: string | null;
  dwell_days?: number | null;
  dwell_stale?: boolean;
  events?: VacancyEventItem[];
  company_contacts?: CompanyContactHint[];
  custom_values?: Record<string, string>;
  custom_fields?: CustomFieldDef[];
  custom_bits?: CustomBit[];
  hunts?: VacancyHuntRef[];
  last_seen_at: string | null;
  language: string | null;
  location: string | null;
};

export type CustomFieldKind = "text" | "number" | "date" | "select" | "check";

export type VacancyHuntRef = {
  id: number;
  name: string;
  pinned: boolean;
  matched: boolean;
};

export type Hunt = {
  id: number;
  name: string;
  enabled: boolean;
  inbox_count: number;
  custom_fields: CustomFieldDef[];
};

export type HuntList = {
  items: Hunt[];
  active_hunt_id: number | null;
};

export type CustomFieldDef = {
  id: string;
  name: string;
  kind: CustomFieldKind;
  options?: string[];
  scope?: "hunt" | "card";
};

export type CustomBit = {
  id: string;
  name: string;
  kind: CustomFieldKind | string;
  value: string;
  scope?: "hunt" | "card";
};

export type CompanyContactHint = {
  telegram_alias?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  label: string;
  vacancy_id?: number | null;
  title?: string | null;
  card_count?: number;
};

export type HuntContact = {
  id: string;
  telegram_alias: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  label: string;
  companies: {
    name: string | null;
    inn?: string | null;
    label?: string;
    org_key?: string | null;
    company_icon?: string | null;
    card_count: number;
    saved: boolean;
  }[];
  cards: {
    id: number;
    title: string;
    company: string | null;
    company_inn?: string | null;
    pipeline_stage: PipelineStage;
  }[];
  saved_ids: number[];
  card_count: number;
  owner_id?: number | null;
  owner_email?: string | null;
};

export type ScraperConfig = {
  id: number;
  name: string;
  source: string;
  enabled: boolean;
  listing_url: string | null;
  query_params: Record<string, unknown>;
  interval_minutes: number;
  max_pages: number;
  last_run?: ScraperRun | null;
  next_run_at?: string | null;
};

export type ScraperRun = {
  id: number;
  scraper_config_id: number | null;
  started_at: string;
  finished_at: string | null;
  status: string;
  found_count: number;
  new_count: number;
  updated_count: number;
  error: string | null;
};

export type Profile = {
  id: number;
  display_name: string | null;
  resume_text: string | null;
  resume_filename: string | null;
  llm_provider: string;
  llm_model: string;
  openai_api_key_set: boolean;
  ollama_base_url: string;
  google_connected?: boolean;
  google_email?: string | null;
  google_client_id_set?: boolean;
  google_redirect_uri?: string | null;
  google_calendar_ready?: boolean;
  google_needs_reconnect?: boolean;
  google_calendar_error?: string | null;
  custom_fields?: CustomFieldDef[];
};

export type CollisionItem = {
  id: number;
  event_id?: number | null;
  company: string | null;
  title: string;
  label?: string | null;
  next_step_at: string;
  ends_at?: string | null;
  next_step_kind: "screening" | "interview" | "offer_deadline" | null;
  match_score: number | null;
  pipeline_stage: PipelineStage;
};

export type CollisionDay = {
  date: string;
  label: string;
  hint: string;
  press_id: number;
  items: CollisionItem[];
};

export type CollisionOut = {
  days: CollisionDay[];
  upcoming: CollisionItem[];
};

export type CalendarPingSlot = {
  id: number;
  thesis_id: number | null;
  label: string;
  card_count: number;
  ping_at: string | null;
  vacancy_ids: number[];
};

export type CalendarBoard = {
  calendar_connected: boolean;
  calendar_ready: boolean;
  collisions: CollisionDay[];
  meetings: CollisionItem[];
  ping_slots: CalendarPingSlot[];
};

export type Thesis = {
  id: number;
  name: string;
  role_query: string;
  grades: string[];
  formats: string[];
  salary_min: number | null;
  no_nda: boolean;
  days: number;
  min_sample: number;
  min_median_match: number;
  enabled: boolean;
  last_verdict: string | null;
  last_reason: string | null;
  last_evaluated_at: string | null;
  custom_fields?: CustomFieldDef[];
  last_wave?: {
    id: number;
    wrote_count: number;
    drafted_count: number;
    size: number;
    sent_at: string | null;
  } | null;
  stats: {
    verdict: string;
    reason: string;
    sample: number;
    median_match: number | null;
    nda_share: number;
    fresh_24h: number;
    outreach: number;
    replies: number;
    age_days: number;
    window_days: number;
  } | null;
};

export type HuntDesk = {
  inbox_total: number;
  waiting_total: number;
  density: { date: string; new: number }[];
};

export type WavePack = {
  inbox_total: number;
  suggested_ids: number[];
  items: Vacancy[];
  pack_default: number;
  pack_max: number;
  last_wave?: Thesis["last_wave"];
};

export type PingSlot = {
  id: number;
  thesis_id: number | null;
  label: string;
  card_count: number;
  ping_at: string | null;
  vacancy_ids?: number[];
  google_event_id?: string | null;
  google_sync_error?: string | null;
  calendar_connected?: boolean;
};

export type NudgeGroup = {
  thesis_id: number | null;
  thesis_name: string | null;
  items: Vacancy[];
  slot?: PingSlot | null;
};

export type NudgeOut = {
  after_days: number;
  total: number;
  calendar_connected?: boolean;
  groups: NudgeGroup[];
};

export const KANBAN: { stage: PipelineStage; label: string }[] = [
  { stage: "to_apply", label: "Откликнуться" },
  { stage: "waiting", label: "Жду ответа" },
  { stage: "screening", label: "Тестовое" },
  { stage: "interview", label: "Тех. собес" },
  { stage: "offer", label: "Оффер" },
  { stage: "rejected", label: "Отказ" },
];

export const STAGE_LABEL: Record<PipelineStage, string> = {
  inbox: "Inbox",
  to_apply: "Откликнуться",
  waiting: "Жду ответа",
  screening: "Тестовое",
  interview: "Тех. собес",
  offer: "Оффер",
  rejected: "Отказ",
  trash: "Мусор",
};

/** Left of the first kanban column is inbox. Right of отказ is nowhere. */
export function adjacentStage(stage: PipelineStage, dir: -1 | 1): PipelineStage | null {
  if (stage === "inbox") return dir === 1 ? "to_apply" : null;
  if (stage === "trash") return dir === -1 ? "inbox" : null;
  const i = KANBAN.findIndex((col) => col.stage === stage);
  if (i < 0) return null;
  const n = i + dir;
  if (n < 0) return "inbox";
  if (n >= KANBAN.length) return null;
  return KANBAN[n].stage;
}
