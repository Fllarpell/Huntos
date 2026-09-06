import type { ReactNode } from "react";

export function PageHead({
  crumb = "HuntOS",
  title,
  count,
  hint,
  children,
}: {
  crumb?: string;
  title: string;
  count?: ReactNode;
  hint?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <p className="crumb">{crumb}</p>
        <div className="mt-1 flex items-baseline gap-2.5">
          <h1 className="page-title">{title}</h1>
          {hint}
          {count != null ? <span className="page-count">{count}</span> : null}
        </div>
      </div>
      {children ? <div className="flex flex-wrap items-center gap-3">{children}</div> : null}
    </div>
  );
}
