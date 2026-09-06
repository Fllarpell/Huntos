"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";

export function HoverMenu({
  label,
  active,
  align = "left",
  children,
}: {
  label: ReactNode;
  active?: boolean;
  align?: "left" | "right";
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    setOpen(false);
    setPinned(false);
  }, [pathname]);

  useEffect(() => {
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, []);

  function place() {
    const el = wrapRef.current;
    const menu = menuRef.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    const width = menu?.offsetWidth || 280;
    let left = align === "right" ? box.right - width : box.left;
    left = Math.min(Math.max(8, left), window.innerWidth - width - 8);
    const next = { top: box.bottom - 6, left };
    setPos((prev) => (prev && prev.top === next.top && prev.left === next.left ? prev : next));
  }

  useLayoutEffect(() => {
    if (!open) return;
    place();
    const onWin = () => place();
    window.addEventListener("resize", onWin);
    window.addEventListener("scroll", onWin, true);
    return () => {
      window.removeEventListener("resize", onWin);
      window.removeEventListener("scroll", onWin, true);
    };
  }, [open, align]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      if (wrapRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
      setPinned(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setOpen(false);
      setPinned(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function clearTimer() {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
  }

  function enter() {
    clearTimer();
    setOpen(true);
  }

  function leave() {
    if (pinned) return;
    timer.current = window.setTimeout(() => setOpen(false), 180);
  }

  function onTriggerClick() {
    clearTimer();
    if (pinned) {
      setPinned(false);
      setOpen(false);
      return;
    }
    setPinned(true);
    setOpen(true);
  }

  const menu =
    mounted && open
      ? createPortal(
          <div
            ref={menuRef}
            className="fixed z-[60]"
            style={{
              top: pos?.top ?? 56,
              left: pos?.left ?? 8,
              visibility: pos ? "visible" : "hidden",
              pointerEvents: pos ? "auto" : "none",
            }}
            onMouseEnter={enter}
            onMouseLeave={leave}
          >
            <div className="mega mt-1.5">{children}</div>
          </div>,
          document.body,
        )
      : null;

  return (
    <div
      ref={wrapRef}
      className="relative flex h-full items-stretch"
      onMouseEnter={enter}
      onMouseLeave={leave}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={onTriggerClick}
        className={`top-link${active || open ? " top-link-on" : ""}`}
      >
        {label}
        <span className="mt-px text-[9px] text-current opacity-50">▾</span>
      </button>
      {menu}
    </div>
  );
}
