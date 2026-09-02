"use client";

import { useEffect, useState } from "react";
import { relativeTime } from "@/lib/format";

export function RelativeTime({ iso }: { iso: string | null }) {
  const [text, setText] = useState("");
  useEffect(() => {
    setText(relativeTime(iso));
  }, [iso]);
  return <span>{text}</span>;
}
