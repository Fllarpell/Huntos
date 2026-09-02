"use client";

import { usePathname } from "next/navigation";
import { HuntProvider } from "@/components/hunt-context";
import { Shell } from "@/components/shell";
import { WorkspaceProvider, useWorkspace } from "@/components/workspace-context";

function WorkspaceApp({ children }: { children: React.ReactNode }) {
  const { asUserId } = useWorkspace();
  const key = asUserId ?? "self";
  return (
    <HuntProvider key={key}>
      <Shell>
        <div key={key}>{children}</div>
      </Shell>
    </HuntProvider>
  );
}

export function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login") {
    return <>{children}</>;
  }
  return (
    <WorkspaceProvider>
      <WorkspaceApp>{children}</WorkspaceApp>
    </WorkspaceProvider>
  );
}
