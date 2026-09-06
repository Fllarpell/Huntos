"use client";

import { usePathname } from "next/navigation";
import { GuideProvider } from "@/components/guide";
import { HuntProvider } from "@/components/hunt-context";
import { OnboardingSheet } from "@/components/onboarding-sheet";
import { Shell } from "@/components/shell";
import { WorkspaceProvider, useWorkspace } from "@/components/workspace-context";

function WorkspaceApp({ children }: { children: React.ReactNode }) {
  const { asUserId } = useWorkspace();
  const key = asUserId ?? "self";
  return (
    <HuntProvider key={key}>
      <Shell>
        <OnboardingSheet />
        <div key={key}>{children}</div>
      </Shell>
    </HuntProvider>
  );
}

export function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login" || pathname.startsWith("/p/")) {
    return <>{children}</>;
  }
  return (
    <WorkspaceProvider>
      <GuideProvider>
        <WorkspaceApp>{children}</WorkspaceApp>
      </GuideProvider>
    </WorkspaceProvider>
  );
}
