export type ResumeBullet = {
  text: string;
  children: string[];
};

export type ResumeJob = {
  company: string;
  title: string;
  period: string;
  context: string;
  bullets: ResumeBullet[];
};

export type ResumeSchool = {
  school: string;
  degree: string;
  period: string;
  bullets: string[];
};

export type ResumeAboutItem = {
  label: string;
  text: string;
};

export type ResumeSkillGroup = {
  label: string;
  items: string;
};

export type ResumeDoc = {
  name: string;
  headline: string;
  email: string;
  phone: string;
  telegram: string;
  location: string;
  links: string[];
  summary: string;
  about_items: ResumeAboutItem[];
  skills: string[];
  skill_groups: ResumeSkillGroup[];
  experience: ResumeJob[];
  education: ResumeSchool[];
  languages: string[];
  courses: string[];
  hackathons: string[];
};

export function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : value == null ? "" : String(value).trim();
}

function asList(value: unknown): string[] {
  if (typeof value === "string") {
    return value
      .split(/\n/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (Array.isArray(value)) return value.map(asText).filter(Boolean);
  return [];
}

function csvList(value: unknown): string[] {
  if (typeof value === "string") {
    return value
      .split(/[,;\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (Array.isArray(value)) return value.map(asText).filter(Boolean);
  return [];
}

export function asBullet(value: unknown): ResumeBullet {
  if (typeof value === "string") {
    return { text: value.trim(), children: [] };
  }
  if (value && typeof value === "object") {
    const row = value as Record<string, unknown>;
    return {
      text: asText(row.text),
      children: asList(row.children),
    };
  }
  return { text: "", children: [] };
}

function asJob(value: unknown): ResumeJob {
  const row = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const bullets = Array.isArray(row.bullets) ? row.bullets.map(asBullet) : [];
  return {
    company: asText(row.company),
    title: asText(row.title),
    period: asText(row.period),
    context: asText(row.context),
    bullets,
  };
}

function asSchool(value: unknown): ResumeSchool {
  const row = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    school: asText(row.school),
    degree: asText(row.degree),
    period: asText(row.period),
    bullets: asList(row.bullets),
  };
}

function asAbout(value: unknown): ResumeAboutItem {
  if (typeof value === "string") {
    const cut = value.indexOf(":");
    if (cut > 0 && cut < 40) {
      return { label: value.slice(0, cut).trim(), text: value.slice(cut + 1).trim() };
    }
    return { label: "", text: value.trim() };
  }
  const row = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return { label: asText(row.label), text: asText(row.text) };
}

function asGroup(value: unknown): ResumeSkillGroup {
  if (typeof value === "string") {
    const cut = value.indexOf(":");
    if (cut > 0 && cut < 48) {
      return { label: value.slice(0, cut).trim(), items: value.slice(cut + 1).trim() };
    }
    return { label: "", items: value.trim() };
  }
  const row = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const items = Array.isArray(row.items) ? csvList(row.items).join(", ") : asText(row.items);
  return { label: asText(row.label || row.name), items };
}

export function emptyResume(): ResumeDoc {
  return {
    name: "",
    headline: "",
    email: "",
    phone: "",
    telegram: "",
    location: "",
    links: [],
    summary: "",
    about_items: [{ label: "", text: "" }],
    skills: [],
    skill_groups: [{ label: "", items: "" }],
    experience: [{ company: "", title: "", period: "", context: "", bullets: [{ text: "", children: [] }] }],
    education: [{ school: "", degree: "", period: "", bullets: [] }],
    languages: [],
    courses: [],
    hackathons: [],
  };
}

export function normalizeResume(raw: unknown): ResumeDoc {
  const src = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const base = emptyResume();
  const experience = Array.isArray(src.experience) ? src.experience.map(asJob) : [];
  const education = Array.isArray(src.education) ? src.education.map(asSchool) : [];
  let about = Array.isArray(src.about_items) ? src.about_items.map(asAbout) : [];
  const languages = csvList(src.languages);
  if (languages.length && !about.some((item) => item.label.toLowerCase().startsWith("язык"))) {
    about = [...about.filter((item) => item.label || item.text), { label: "Языки", text: languages.join(", ") }];
  }
  let groups = Array.isArray(src.skill_groups) ? src.skill_groups.map(asGroup) : [];
  const skills = csvList(src.skills);
  if (!groups.some((g) => g.label || g.items) && skills.length) {
    groups = [{ label: "", items: skills.join(", ") }];
  }
  return {
    name: asText(src.name) || base.name,
    headline: asText(src.headline),
    email: asText(src.email),
    phone: asText(src.phone),
    telegram: asText(src.telegram),
    location: asText(src.location),
    links: asList(src.links),
    summary: asText(src.summary),
    about_items: about.length ? about : base.about_items,
    skills,
    skill_groups: groups.length ? groups : base.skill_groups,
    experience: experience.length ? experience : base.experience,
    education: education.length ? education : base.education,
    languages,
    courses: asList(src.courses),
    hackathons: asList(src.hackathons),
  };
}

export function resumeHasContent(doc: ResumeDoc): boolean {
  if (doc.name || doc.headline || doc.summary || doc.email || doc.phone || doc.telegram) return true;
  if (doc.about_items.some((item) => item.label || item.text)) return true;
  if (doc.skill_groups.some((g) => g.label || g.items) || doc.skills.length) return true;
  if (doc.experience.some((job) => job.company || job.title || job.bullets.some((b) => b.text))) return true;
  if (doc.education.some((row) => row.school || row.degree)) return true;
  if (doc.courses.length || doc.hackathons.length) return true;
  return false;
}

export function linesToText(items: string[]): string {
  return items.join("\n");
}

export function textToLines(value: string): string[] {
  return value.split("\n");
}

export function tidyLine(value: string): string {
  return value.replace(/^[-•–*]\s+/, "").trim();
}

export function bulletsToText(bullets: ResumeBullet[]): string {
  const lines: string[] = [];
  for (const bullet of bullets) {
    lines.push(bullet.text);
    for (const child of bullet.children) lines.push(`  ${child}`);
  }
  return lines.join("\n");
}

export function textToBullets(value: string): ResumeBullet[] {
  const rows: ResumeBullet[] = [];
  for (const raw of value.split("\n")) {
    if (/^[ \t]/.test(raw) && rows.length) {
      rows[rows.length - 1].children.push(raw.replace(/^[ \t]+/, ""));
      continue;
    }
    rows.push({ text: raw, children: [] });
  }
  return rows.length ? rows : [{ text: "", children: [] }];
}

export function telegramHref(value: string): string | null {
  const raw = value.trim();
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw)) return raw;
  const handle = raw.replace(/^@/, "").replace(/^t\.me\//i, "").replace(/^https?:\/\/t\.me\//i, "");
  return handle ? `https://t.me/${handle}` : null;
}

export function telegramLabel(value: string): string {
  const raw = value.trim();
  if (!raw) return "";
  if (raw.startsWith("@")) return raw;
  const handle = raw.replace(/^https?:\/\/t\.me\//i, "").replace(/^t\.me\//i, "");
  return handle ? `@${handle.replace(/^@/, "")}` : raw;
}

export function linkHref(value: string): string | null {
  const raw = value.trim();
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw)) return raw;
  if (/^[\w.-]+\.[a-z]{2,}/i.test(raw) && !raw.includes(" ")) return `https://${raw}`;
  return null;
}
