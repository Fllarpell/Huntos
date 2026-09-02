"use client";

import { useEffect } from "react";
import { installExtensionNoiseGuard } from "@/lib/extension-noise";

/** Extra pass after mount — instrumentation-client already ran before hydrate. */
export function IgnoreExtensionNoise() {
  useEffect(() => {
    installExtensionNoiseGuard();
  }, []);
  return null;
}
