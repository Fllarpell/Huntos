"use client";

import type { ReactNode } from "react";
import { PT_Sans } from "next/font/google";
import {
  linkHref,
  resumeHasContent,
  telegramHref,
  telegramLabel,
  type ResumeDoc,
} from "@/lib/resume";

const ptSans = PT_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "700"],
  style: ["normal", "italic"],
});

function BoldBits({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, index) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={index}>{part.slice(2, -2)}</strong>
        ) : (
          part
        ),
      )}
    </>
  );
}

function MailLink({ email }: { email: string }) {
  return (
    <a href={`mailto:${email}`} className="resume-a">
      {email}
    </a>
  );
}

function TgLink({ value }: { value: string }) {
  const href = telegramHref(value);
  const label = telegramLabel(value);
  if (!href) return <>{label || value}</>;
  return (
    <a href={href} className="resume-a">
      {label}
    </a>
  );
}

function ExtraLink({ value }: { value: string }) {
  const href = linkHref(value);
  if (!href) return <>{value}</>;
  return (
    <a href={href} className="resume-a">
      {value.replace(/^https?:\/\//i, "")}
    </a>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="resume-sec">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function ResumeSheet({ doc }: { doc: ResumeDoc }) {
  const contacts: ReactNode[] = [];
  if (doc.location) contacts.push(doc.location);
  if (doc.phone) contacts.push(<>Телефон: {doc.phone}</>);
  if (doc.telegram) {
    contacts.push(
      <>
        Telegram: <TgLink value={doc.telegram} />
      </>,
    );
  }
  if (doc.email) {
    contacts.push(
      <>
        Email: <MailLink email={doc.email} />
      </>,
    );
  }

  const aboutItems = doc.about_items.filter((item) => item.label || item.text);
  const groups = doc.skill_groups.filter((g) => g.label || g.items);
  const jobs = doc.experience.filter(
    (job) => job.company || job.title || job.bullets.some((b) => b.text || b.children.length),
  );
  const schools = doc.education.filter((row) => row.school || row.degree || row.bullets.length);

  if (!resumeHasContent(doc)) {
    return (
      <article id="resume-sheet" className={`resume-sheet resume-paper ${ptSans.className}`}>
        <p className="resume-empty">Слева поля — справа лист как в LaTeX. PDF печатает этот лист.</p>
      </article>
    );
  }

  return (
    <article id="resume-sheet" className={`resume-sheet resume-paper ${ptSans.className}`}>
      <header className="resume-hero">
        {doc.name ? <h1>{doc.name}</h1> : null}
        {doc.headline ? <p className="resume-role">{doc.headline}</p> : null}
        {contacts.length ? (
          <p className="resume-contacts">
            {contacts.map((bit, index) => (
              <span key={index}>
                {index > 0 ? <span className="resume-sep"> | </span> : null}
                {bit}
              </span>
            ))}
          </p>
        ) : null}
        {doc.links.length ? (
          <p className="resume-contacts">
            {doc.links.map((item, index) => (
              <span key={item}>
                {index > 0 ? <span className="resume-sep"> | </span> : null}
                <ExtraLink value={item} />
              </span>
            ))}
          </p>
        ) : null}
      </header>

      {doc.summary || aboutItems.length ? (
        <Section title="Обо мне">
          {doc.summary ? <p className="resume-lead">{doc.summary}</p> : null}
          {aboutItems.length ? (
            <ul>
              {aboutItems.map((item, index) => (
                <li key={`${item.label}-${index}`}>
                  {item.label ? <strong>{item.label}: </strong> : null}
                  <BoldBits text={item.text} />
                </li>
              ))}
            </ul>
          ) : null}
        </Section>
      ) : null}

      {groups.length ? (
        <Section title="Технические навыки">
          <ul>
            {groups.map((group, index) => (
              <li key={`${group.label}-${index}`}>
                {group.label ? <strong>{group.label}: </strong> : null}
                {group.items}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {jobs.length ? (
        <Section title="Опыт работы">
          {jobs.map((job, index) => (
            <div key={`${job.company}-${index}`} className="resume-job">
              <p className="resume-row">
                <strong>{job.company || job.title}</strong>
                {job.period ? <strong>{job.period}</strong> : <span />}
              </p>
              {job.title || job.context ? (
                <p className="resume-row resume-italic">
                  <span>{job.company ? job.title : ""}</span>
                  <span>{job.context}</span>
                </p>
              ) : null}
              {job.bullets.some((b) => b.text.trim() || b.children.some((child) => child.trim())) ? (
                <ul>
                  {job.bullets.map((bullet, bIndex) =>
                    bullet.text.trim() || bullet.children.some((child) => child.trim()) ? (
                      <li key={bIndex}>
                        <BoldBits text={bullet.text} />
                        {bullet.children.some((child) => child.trim()) ? (
                          <ul>
                            {bullet.children.map((child, cIndex) =>
                              child.trim() ? (
                                <li key={cIndex}>
                                  <BoldBits text={child} />
                                </li>
                              ) : null,
                            )}
                          </ul>
                        ) : null}
                      </li>
                    ) : null,
                  )}
                </ul>
              ) : null}
            </div>
          ))}
        </Section>
      ) : null}

      {schools.length ? (
        <Section title="Образование">
          {schools.map((row, index) => (
            <div key={`${row.school}-${index}`} className="resume-job">
              <p className="resume-row">
                <strong>{row.school}</strong>
                {row.period ? <strong>{row.period}</strong> : <span />}
              </p>
              {row.degree ? <p className="resume-italic">{row.degree}</p> : null}
              {row.bullets.some((item) => item.trim()) ? (
                <ul>
                  {row.bullets.map((item, bIndex) =>
                    item.trim() ? (
                      <li key={bIndex}>
                        <BoldBits text={item} />
                      </li>
                    ) : null,
                  )}
                </ul>
              ) : null}
            </div>
          ))}
        </Section>
      ) : null}

      {doc.courses.length ? (
        <Section title="Повышение квалификации">
          <ul>
            {doc.courses.map((item) => (
              <li key={item}>
                <BoldBits text={item} />
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {doc.hackathons.length ? (
        <Section title="Хакатоны">
          <ul>
            {doc.hackathons.map((item) => (
              <li key={item}>
                <BoldBits text={item} />
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </article>
  );
}
