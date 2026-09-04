"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { usePathname, useRouter } from "next/navigation";
import {
  FIRST_TOUR,
  GUIDE,
  clearPendingFirstTour,
  markGuideFirstDone,
  pageTourSteps,
  pageTourTitle,
  setGuideMuted,
  shouldAutoStartFirstTour,
  type TourStep,
} from "@/lib/guide";
import { useWorkspace } from "@/components/workspace-context";

type TourKind = "first" | "page" | "spot";

type GuideApi = {
  register: (id: string, node: HTMLElement | null) => void;
  start: (ids: string[]) => void;
  startPage: () => void;
  startFirst: () => void;
  show: (id: string) => void;
  close: () => void;
  active: boolean;
};

const GuideCtx = createContext<GuideApi | null>(null);

export function useGuide(): GuideApi {
  const ctx = useContext(GuideCtx);
  if (!ctx) throw new Error("GuideProvider missing");
  return ctx;
}

function useGuideOptional(): GuideApi | null {
  return useContext(GuideCtx);
}

type Rect = { top: number; left: number; width: number; height: number };

function measure(node: HTMLElement): Rect {
  const box = node.getBoundingClientRect();
  const pad = 6;
  return {
    top: Math.max(8, box.top - pad),
    left: Math.max(8, box.left - pad),
    width: Math.min(window.innerWidth - 16, box.width + pad * 2),
    height: Math.min(window.innerHeight - 16, box.height + pad * 2),
  };
}

function tooltipPos(hole: Rect, width: number, height: number) {
  const gap = 12;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let top = hole.top + hole.height + gap;
  let left = Math.min(Math.max(16, hole.left), vw - width - 16);
  if (top + height > vh - 16) {
    top = hole.top - height - gap;
  }
  if (top < 16) {
    top = Math.min(vh - height - 16, Math.max(16, hole.top));
    left = hole.left + hole.width + gap;
    if (left + width > vw - 16) left = hole.left - width - gap;
  }
  left = Math.min(Math.max(16, left), vw - width - 16);
  top = Math.min(Math.max(16, top), vh - height - 16);
  return { top, left };
}

export function GuideProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { me, asUserId } = useWorkspace();
  const guideUserId = me && !asUserId ? me.id : null;
  const nodes = useRef(new Map<string, HTMLElement>());
  const navigating = useRef(false);
  const autoStarted = useRef(false);
  const [queue, setQueue] = useState<TourStep[]>([]);
  const [index, setIndex] = useState(0);
  const [kind, setKind] = useState<TourKind>("page");
  const [hole, setHole] = useState<Rect | null>(null);
  const [ready, setReady] = useState(false);
  const queueRef = useRef(queue);
  const indexRef = useRef(index);
  const kindRef = useRef(kind);
  const activeIdRef = useRef<string | null>(null);
  queueRef.current = queue;
  indexRef.current = index;
  kindRef.current = kind;

  const finish = useCallback(
    (opts?: { mute?: boolean }) => {
      if (guideUserId != null) {
        if (kindRef.current === "first" || opts?.mute) markGuideFirstDone(guideUserId);
        if (opts?.mute) setGuideMuted(guideUserId, true);
        if (kindRef.current === "first" || opts?.mute) clearPendingFirstTour();
      }
      navigating.current = false;
      setQueue([]);
      setIndex(0);
      setHole(null);
    },
    [guideUserId],
  );

  const close = useCallback(() => finish(), [finish]);

  const applyIndex = useCallback(
    (nextIndex: number, steps: TourStep[]) => {
      const step = steps[nextIndex];
      if (!step) {
        finish();
        return;
      }
      const href = step.href;
      if (href && href !== pathname) {
        navigating.current = true;
        setHole(null);
        setIndex(nextIndex);
        router.push(href);
        return;
      }
      setIndex(nextIndex);
    },
    [finish, pathname, router],
  );

  const begin = useCallback(
    (steps: TourStep[], tour: TourKind) => {
      const next = steps.filter((step) => GUIDE[step.id]);
      if (!next.length) return;
      kindRef.current = tour;
      setKind(tour);
      setQueue(next);
      applyIndex(0, next);
    },
    [applyIndex],
  );

  const start = useCallback(
    (ids: string[]) => {
      begin(
        ids.map((id) => ({ id })),
        "page",
      );
    },
    [begin],
  );

  const startPage = useCallback(() => {
    begin(pageTourSteps(pathname), "page");
  }, [begin, pathname]);

  const startFirst = useCallback(() => {
    begin(FIRST_TOUR, "first");
  }, [begin]);

  const show = useCallback((id: string) => {
    if (!GUIDE[id] || !nodes.current.has(id)) return;
    kindRef.current = "spot";
    setKind("spot");
    setQueue([{ id }]);
    setIndex(0);
  }, []);

  const register = useCallback((id: string, node: HTMLElement | null) => {
    if (node) nodes.current.set(id, node);
    else nodes.current.delete(id);
    if (id === activeIdRef.current && node) {
      node.scrollIntoView({ block: "nearest", inline: "nearest" });
      setHole(measure(node));
    }
  }, []);

  const activeId = queue[index]?.id || null;
  activeIdRef.current = activeId;

  const syncHole = useCallback(() => {
    if (!activeId) {
      setHole(null);
      return;
    }
    const node = nodes.current.get(activeId);
    if (!node) {
      setHole(null);
      return;
    }
    node.scrollIntoView({ block: "nearest", inline: "nearest" });
    setHole(measure(node));
  }, [activeId]);

  useEffect(() => {
    if (!activeId || !queue.length) return;
    if (nodes.current.get(activeId)) return;
    const href = queue[index]?.href;
    if (href && href !== pathname) return;
    const timer = window.setTimeout(() => {
      if (nodes.current.get(activeId)) {
        syncHole();
        return;
      }
      if (index >= queue.length - 1) finish();
      else applyIndex(index + 1, queue);
    }, 900);
    return () => window.clearTimeout(timer);
  }, [activeId, applyIndex, finish, index, pathname, queue, syncHole]);

  useEffect(() => {
    syncHole();
    if (!activeId) return;
    const onWin = () => syncHole();
    window.addEventListener("resize", onWin);
    window.addEventListener("scroll", onWin, true);
    const timer = window.setInterval(syncHole, 250);
    return () => {
      window.removeEventListener("resize", onWin);
      window.removeEventListener("scroll", onWin, true);
      window.clearInterval(timer);
    };
  }, [activeId, syncHole, pathname]);

  useEffect(() => {
    setReady(true);
  }, []);

  useEffect(() => {
    const steps = queueRef.current;
    if (!steps.length) return;
    const href = steps[indexRef.current]?.href;
    if (href) {
      if (pathname === href) {
        navigating.current = false;
        const timer = window.setTimeout(syncHole, 400);
        return () => window.clearTimeout(timer);
      }
      if (navigating.current) return;
      finish();
      return;
    }
    if (kindRef.current === "page" || kindRef.current === "spot") finish();
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps -- abort page tour on manual nav

  useEffect(() => {
    autoStarted.current = false;
  }, [guideUserId]);

  useEffect(() => {
    if (!ready || autoStarted.current || guideUserId == null) return;
    if (!shouldAutoStartFirstTour(guideUserId)) {
      autoStarted.current = true;
      return;
    }
    const timer = window.setTimeout(() => {
      if (autoStarted.current || guideUserId == null || !shouldAutoStartFirstTour(guideUserId)) return;
      autoStarted.current = true;
      startFirst();
    }, 700);
    return () => window.clearTimeout(timer);
  }, [pathname, ready, startFirst, guideUserId]);

  useEffect(() => {
    if (!queue.length) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
      if (event.key === "ArrowRight" || event.key === "Enter") {
        event.preventDefault();
        if (index >= queue.length - 1) close();
        else applyIndex(index + 1, queue);
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        applyIndex(Math.max(0, index - 1), queue);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [applyIndex, close, index, queue]);

  const api = useMemo<GuideApi>(
    () => ({ register, start, startPage, startFirst, show, close, active: queue.length > 0 }),
    [register, start, startPage, startFirst, show, close, queue.length],
  );

  const copy = activeId ? GUIDE[activeId] : null;
  const step = queue.length ? index + 1 : 0;
  const tourLabel = kind === "first" ? "Основы HuntOS" : kind === "page" ? pageTourTitle(pathname) : null;

  return (
    <GuideCtx.Provider value={api}>
      {children}
      {ready && copy && hole
        ? createPortal(
            <GuideOverlay
              copy={copy}
              hole={hole}
              step={step}
              total={queue.length}
              label={tourLabel}
              onPrev={() => applyIndex(Math.max(0, index - 1), queue)}
              onNext={() => {
                if (index >= queue.length - 1) close();
                else applyIndex(index + 1, queue);
              }}
              onClose={close}
              onMute={kind === "first" ? () => finish({ mute: true }) : undefined}
            />,
            document.body,
          )
        : null}
    </GuideCtx.Provider>
  );
}

function GuideOverlay({
  copy,
  hole,
  step,
  total,
  label,
  onPrev,
  onNext,
  onClose,
  onMute,
}: {
  copy: { title: string; body: string };
  hole: Rect;
  step: number;
  total: number;
  label: string | null;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
  onMute?: () => void;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState({ top: hole.top + hole.height + 12, left: hole.left });

  useEffect(() => {
    const card = cardRef.current;
    if (!card) return;
    setTip(tooltipPos(hole, card.offsetWidth || 320, card.offsetHeight || 180));
  }, [hole, copy.title]);

  const last = step >= total;

  return (
    <div className="fixed inset-0 z-[90]" role="dialog" aria-modal="true" aria-labelledby="guide-title">
      <button type="button" className="absolute inset-0 cursor-default bg-transparent" aria-label="Закрыть обучение" onClick={onClose} />
      <div
        className="guide-hole pointer-events-none absolute rounded-2xl"
        style={{ top: hole.top, left: hole.left, width: hole.width, height: hole.height }}
      />
      <div
        ref={cardRef}
        className="absolute w-[min(320px,calc(100vw-32px))] rounded-2xl border border-line bg-bg-soft p-4 shadow-[0_16px_60px_rgba(0,0,0,0.45)]"
        style={{ top: tip.top, left: tip.left }}
      >
        {label ? <p className="text-[11px] tracking-[0.12em] text-muted uppercase">{label}</p> : null}
        <p id="guide-title" className={`${label ? "mt-1" : ""} text-[15px] font-medium tracking-tight`}>
          {copy.title}
        </p>
        <p className="mt-2 text-[13px] leading-5 text-muted">{copy.body}</p>
        <div className="mt-4 flex items-center gap-3">
          {total > 1 ? (
            <span className="text-[11px] tabular-nums text-muted">
              {step}/{total}
            </span>
          ) : null}
          {total > 1 && step > 1 ? (
            <button type="button" className="text-[13px] text-muted hover:text-white" onClick={onPrev}>
              Назад
            </button>
          ) : null}
          <button type="button" className="text-[13px] text-accent" onClick={onNext}>
            {last ? "Понятно" : "Дальше"}
          </button>
          <button type="button" className="ml-auto text-[12px] text-muted hover:text-white" onClick={onClose}>
            Закрыть
          </button>
        </div>
        {onMute && total > 1 && step === 1 ? (
          <button type="button" className="mt-3 text-[12px] text-muted/80 hover:text-muted" onClick={onMute}>
            Больше не показывать само
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function GuideSpot({
  id,
  children,
  className,
}: {
  id: string;
  children: ReactNode;
  className?: string;
}) {
  const ctx = useGuideOptional();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ctx) return;
    ctx.register(id, ref.current);
    return () => ctx.register(id, null);
  }, [ctx, id]);

  if (!GUIDE[id]) return <>{children}</>;
  return (
    <div ref={ref} data-guide={id} className={className}>
      {children}
    </div>
  );
}

export function GuideHint(_props: { id: string; className?: string }) {
  return null;
}

export function GuideHeading({
  id,
  children,
  className,
}: {
  id: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <GuideSpot id={id} className={className}>
      {children}
    </GuideSpot>
  );
}

export function GuideLabel({
  id,
  children,
  className,
}: {
  id: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <GuideSpot id={id}>
      <span className={className}>{children}</span>
    </GuideSpot>
  );
}
