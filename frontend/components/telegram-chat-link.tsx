"use client";

import { displayUrl } from "@/lib/format";

export function ExternalTextLink({
  href,
  className = "",
}: {
  href: string | null | undefined;
  className?: string;
}) {
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => e.stopPropagation()}
      className={`truncate text-accent hover:underline ${className}`}
    >
      {displayUrl(href)}
    </a>
  );
}

export function TelegramChatLink(props: { href: string | null | undefined; className?: string }) {
  return <ExternalTextLink {...props} />;
}
