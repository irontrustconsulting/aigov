"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/dashboard", label: "Portfolio" },
  { href: "/review-queue", label: "Review queue" },
  { href: "/evidence", label: "Evidence" },
  { href: "/audit", label: "Audit" },
];

export function AppNav() {
  const pathname = usePathname();

  return (
    <header className="border-hairline border-b px-6 py-3">
      <div className="mx-auto flex max-w-4xl items-center gap-6">
        <Link href="/dashboard" className="text-sm font-semibold">
          IronTrust
        </Link>
        <nav aria-label="primary" className="flex gap-4">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`text-sm ${active ? "font-medium" : "text-ink-muted hover:text-ink"}`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
