"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, GraduationCap, Inbox, Kanban, Settings, Target, Trophy, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { GuideSpot, useGuide } from "@/components/guide";
import { pageTourTitle } from "@/lib/guide";
import { HuntSwitcher } from "@/components/hunt-switcher";
import { WorkspaceSwitcher } from "@/components/workspace-switcher";
import { FeedbackButtons } from "@/components/feedback";
import { ChatEntry } from "@/components/chat-panel";
import { useHunt } from "@/components/hunt-context";
import { useWorkspace } from "@/components/workspace-context";

const NAV = [
  { href: "/", label: "Inbox", icon: Inbox },
  { href: "/pipeline", label: "Воронка", icon: Kanban },
  { href: "/time", label: "Время", icon: CalendarDays },
  { href: "/contacts", label: "Контакты", icon: Users },
  { href: "/internships", label: "Стажировки", icon: GraduationCap },
  { href: "/hackathons", label: "Хакатоны", icon: Trophy },
  { href: "/thesis", label: "Тезис", icon: Target },
  { href: "/settings", label: "Настройки", icon: Settings },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { activeHuntId } = useHunt();
  const { me } = useWorkspace();
  const guide = useGuide();
  const [inboxCount, setInboxCount] = useState<number | null>(null);
  const [nudgeCount, setNudgeCount] = useState<number | null>(null);

  useEffect(() => {
    if (!me) return;
    api
      .vacancies({ stage: "inbox", limit: 1, hunt_id: activeHuntId })
      .then((r) => setInboxCount(r.total))
      .catch(() => setInboxCount(null));
    api
      .nudge(activeHuntId)
      .then((r) => setNudgeCount(r.total))
      .catch(() => setNudgeCount(null));
  }, [pathname, me, activeHuntId]);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-[220px] shrink-0 flex-col border-r border-line bg-bg-soft px-4 py-6">
        <div className="mb-10 px-2">
          <div className="text-[13px] tracking-[0.18em] text-muted uppercase">Job CRM</div>
          <div className="mt-1 text-xl font-semibold tracking-tight">HuntOS</div>
          <GuideSpot id="shell.hunt">
            <HuntSwitcher />
          </GuideSpot>
          <WorkspaceSwitcher />
        </div>
        <GuideSpot id="shell.nav" className="flex min-h-0 flex-1 flex-col">
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] transition ${
                  active ? "bg-white/6 text-white" : "text-muted hover:bg-white/4 hover:text-white"
                }`}
              >
                <Icon size={18} strokeWidth={1.7} />
                <span className="flex-1">{item.label}</span>
                {item.href === "/" && inboxCount != null && (
                  <span className="rounded-full bg-white/8 px-2 py-0.5 text-[11px] text-muted">
                    {inboxCount}
                  </span>
                )}
                {item.href === "/pipeline" && nudgeCount != null && nudgeCount > 0 && (
                  <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-[11px] text-amber-100">
                    {nudgeCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        </GuideSpot>
        <div className="mt-4 border-t border-line px-2 pt-4">
          <div className="space-y-2">
            <ChatEntry />
            <FeedbackButtons />
            <GuideSpot id="shell.guide">
              <button
                type="button"
                onClick={() => guide.startPage()}
                className="block w-full text-left text-[13px] leading-5 text-muted hover:text-white"
              >
                Обучение
                <span className="mt-0.5 block text-[12px] text-accent/80">{pageTourTitle(pathname)}</span>
              </button>
            </GuideSpot>
          </div>
          {me && (
            <div className="mt-4 border-t border-white/[0.06] pt-4">
              <p className="truncate text-[12px] leading-5 text-muted">{me.email}</p>
              <button
                type="button"
                onClick={async () => {
                  await api.logout();
                  window.location.href = "/login";
                }}
                className="mt-2 text-[13px] text-muted hover:text-white"
              >
                Выйти
              </button>
            </div>
          )}
        </div>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
