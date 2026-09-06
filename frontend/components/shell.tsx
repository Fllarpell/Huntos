"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { GuideSpot, useGuide } from "@/components/guide";
import { pageTourTitle } from "@/lib/guide";
import { HuntSwitcher } from "@/components/hunt-switcher";
import { WorkspaceSwitcher } from "@/components/workspace-switcher";
import { FeedbackButtons } from "@/components/feedback";
import { ChatEntry } from "@/components/chat-panel";
import { HoverMenu } from "@/components/hover-menu";
import { useHunt } from "@/components/hunt-context";
import { useWorkspace } from "@/components/workspace-context";

const LINKS = [
  { href: "/", label: "inbox" },
  { href: "/pipeline", label: "воронка" },
] as const;

const CABINET = [
  { href: "/resume", label: "резюме", detail: "ATS-вид, PDF, Fit по вакансиям" },
  { href: "/time", label: "время", detail: "собесы, дедлайны, пинги" },
  { href: "/contacts", label: "контакты", detail: "HR и компании с карточек" },
  { href: "/thesis", label: "направления", detail: "какие вакансии смотришь" },
  { href: "/internships", label: "стажировки", detail: "программы и школы" },
  { href: "/hackathons", label: "хакатоны", detail: "ивенты в одном списке" },
] as const;

function pathIn(pathname: string, href: string) {
  return pathname === href;
}

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

  const cabinetOn = CABINET.some((item) => pathIn(pathname, item.href));
  const accountLabel = me?.email?.split("@")[0] || "аккаунт";

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b border-line bg-bg print:hidden">
        <div className="flex h-14 items-stretch gap-5 px-4 md:px-6">
          <Link href="/" className="flex items-center text-[15px] font-semibold tracking-tight">
            HuntOS
          </Link>
          <GuideSpot id="shell.nav" className="flex min-w-0 flex-1 items-stretch gap-4 overflow-x-auto md:overflow-visible">
            {LINKS.map((item) => {
              const on = pathIn(pathname, item.href);
              return (
                <Link key={item.href} href={item.href} className={`top-link${on ? " top-link-on" : ""}`}>
                  {item.label}
                  {item.href === "/" && inboxCount != null ? (
                    <span className="text-[11px] tabular-nums text-muted">{inboxCount}</span>
                  ) : null}
                  {item.href === "/pipeline" && nudgeCount != null && nudgeCount > 0 ? (
                    <span className="text-[11px] tabular-nums text-amber-200">{nudgeCount}</span>
                  ) : null}
                </Link>
              );
            })}
            <HoverMenu label="кабинет" active={cabinetOn}>
              {CABINET.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  data-on={pathIn(pathname, item.href) ? "true" : undefined}
                  className="mega-item"
                >
                  <span className="mega-k">{item.label}</span>
                  <span className="mega-d">{item.detail}</span>
                </Link>
              ))}
            </HoverMenu>
            <Link
              href="/settings"
              className={`top-link${pathIn(pathname, "/settings") ? " top-link-on" : ""}`}
            >
              настройки
            </Link>
          </GuideSpot>
          <div className="ml-auto hidden items-stretch md:flex">
            <GuideSpot id="shell.hunt">
              <HuntSwitcher variant="bar" />
            </GuideSpot>
          </div>
          <ChatEntry className="top-link" label="чат" />
          <HoverMenu label={accountLabel} align="right" active={false}>
              {me ? (
                <p className="px-3 pt-1.5 pb-2 text-[12px] text-muted">{me.email}</p>
              ) : null}
              <div className="md:hidden border-b border-line pb-1 mb-1">
                <p className="px-3 pb-1 text-[11px] text-muted">направление</p>
                <HuntSwitcher variant="block" />
              </div>
              <WorkspaceSwitcher variant="menu" />
              <GuideSpot id="shell.guide">
                <button type="button" onClick={() => guide.startPage()} className="mega-item">
                  <span className="mega-k">обучение</span>
                  <span className="mega-d">{pageTourTitle(pathname)}</span>
                </button>
              </GuideSpot>
              <FeedbackButtons itemClassName="mega-item" />
              {me ? (
                <button
                  type="button"
                  className="mega-item"
                  onClick={async () => {
                    await api.logout();
                    window.location.href = "/login";
                  }}
                >
                  <span className="mega-k">выйти</span>
                </button>
              ) : null}
            </HoverMenu>
        </div>
      </header>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-bg">{children}</main>
    </div>
  );
}
