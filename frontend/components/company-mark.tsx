"use client";

import { useState } from "react";
import type { Vacancy } from "@/lib/types";
import { companyInitial } from "@/lib/format";

type MarkSource = {
  company?: string | null;
  company_icon?: string | null;
};

function isHttpIcon(src: string | null | undefined) {
  return Boolean(src && /^https?:\/\//i.test(src));
}

export function CompanyMark({
  vacancy,
  company,
  icon,
  size = 36,
}: {
  vacancy?: Pick<Vacancy, "company" | "company_icon"> | MarkSource;
  company?: string | null;
  icon?: string | null;
  size?: number;
}) {
  const [broken, setBroken] = useState(false);
  const name = company ?? vacancy?.company ?? null;
  const src = icon ?? vacancy?.company_icon ?? null;
  const px = `${size}px`;
  if (!broken && isHttpIcon(src)) {
    return (
      <img
        src={src as string}
        alt=""
        width={size}
        height={size}
        className="rounded-lg object-cover"
        style={{ width: px, height: px }}
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-lg bg-white/8 text-[13px] font-medium text-white/80"
      style={{ width: px, height: px }}
    >
      {companyInitial(name)}
    </div>
  );
}
