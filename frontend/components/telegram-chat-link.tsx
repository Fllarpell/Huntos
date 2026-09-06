"use client";

import type { ReactNode } from "react";
import { displayUrl } from "@/lib/format";
import { onExternalClick } from "@/lib/open-url";

export function ExternalTextLink({
  href,
  className = "",
  children,
}: {
  href: string | null | undefined;
  className?: string;
  children?: ReactNode;
}) {
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => onExternalClick(href, e)}
      className={`truncate text-accent hover:underline ${className}`}
    >
      {children ?? displayUrl(href)}
    </a>
  );
}

export function TelegramChatLink(props: { href: string | null | undefined; className?: string }) {
  return <ExternalTextLink {...props} />;
}
