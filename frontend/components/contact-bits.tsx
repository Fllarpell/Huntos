"use client";

import { vacancyTelegramUrl, telegramHandle, telHref } from "@/lib/format";
import type { Vacancy } from "@/lib/types";
import { TelegramChatLink } from "./telegram-chat-link";

function MailLink({ email, className = "" }: { email: string; className?: string }) {
  return (
    <a
      href={`mailto:${email}`}
      onClick={(e) => e.stopPropagation()}
      className={`truncate text-accent hover:underline ${className}`}
    >
      {email}
    </a>
  );
}

function PhoneLink({ phone, className = "" }: { phone: string; className?: string }) {
  return (
    <a
      href={telHref(phone)}
      onClick={(e) => e.stopPropagation()}
      className={`truncate text-accent hover:underline ${className}`}
    >
      {phone}
    </a>
  );
}

export function ContactBits({
  vacancy,
  className = "",
}: {
  vacancy: Pick<Vacancy, "telegram_alias" | "telegram_url" | "contact_email" | "contact_phone">;
  className?: string;
}) {
  const chat = vacancyTelegramUrl(vacancy);
  const handle = telegramHandle(vacancy.telegram_alias);
  const email = (vacancy.contact_email || "").trim();
  const phone = (vacancy.contact_phone || "").trim();
  if (!chat && !email && !phone) return null;
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] ${className}`}>
      {chat && <TelegramChatLink href={chat} />}
      {!chat && handle && <span className="text-muted">{handle}</span>}
      {email && <MailLink email={email} />}
      {phone && <PhoneLink phone={phone} />}
    </div>
  );
}

export function hasContact(vacancy: Pick<Vacancy, "telegram_alias" | "telegram_url" | "contact_email" | "contact_phone">) {
  return Boolean(
    vacancyTelegramUrl(vacancy) || (vacancy.contact_email || "").trim() || (vacancy.contact_phone || "").trim(),
  );
}
