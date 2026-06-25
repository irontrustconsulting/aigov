import { type ReactNode } from "react";

export interface SidebarNavItem {
  href: string;
  label: string;
  /** Caller computes active state (e.g. via usePathname in the app). */
  isActive?: boolean;
}

export interface SidebarProps {
  brand: ReactNode;
  /** Simple nav items rendered automatically. Omit when using the `nav` slot. */
  navItems?: SidebarNavItem[];
  /** Custom nav content (e.g. RequirePermission-gated items). Takes precedence over `navItems`. */
  nav?: ReactNode;
  foot: ReactNode;
  /** CSS custom-property value for the sidebar background rail.
   *  Operator plane sets "var(--chrome-rail-bg)" (INV-60). */
  railBg?: string;
}

export function Sidebar({ brand, navItems, nav, foot, railBg }: SidebarProps) {
  const defaultNav = navItems ? (
    <nav aria-label="Primary navigation">
      <ul className="space-y-0.5" role="list">
        {navItems.map((item) => (
          <li key={item.href}>
            <a
              href={item.href}
              aria-current={item.isActive ? "page" : undefined}
              className={[
                "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
                item.isActive
                  ? "bg-brand text-surface"
                  : "text-ink hover:bg-surface-sunken",
              ].join(" ")}
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  ) : null;

  return (
    <aside
      className="flex h-full w-56 flex-shrink-0 flex-col border-r border-hairline"
      style={railBg ? { backgroundColor: railBg } : undefined}
    >
      <div className="flex flex-1 flex-col justify-between overflow-y-auto px-3 py-4">
        <div className="space-y-6">
          <div className="px-1">{brand}</div>
          {nav ?? defaultNav}
        </div>

        <div className="border-t border-hairline pt-3">{foot}</div>
      </div>
    </aside>
  );
}
