"use client";

import type { CustomBit } from "@/lib/types";

export function CustomFieldChips({ bits, className = "" }: { bits?: CustomBit[]; className?: string }) {
  if (!bits?.length) return null;
  return (
    <p className={`flex flex-wrap gap-x-2 gap-y-0.5 text-[12px] text-muted ${className}`}>
      {bits.map((bit) => (
        <span key={bit.id} className="truncate">
          {bit.kind === "check" ? bit.name : `${bit.name} ${bit.value}`}
        </span>
      ))}
    </p>
  );
}
