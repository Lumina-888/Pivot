import Link from "next/link";
import type { ReactNode } from "react";

type AdminItem = { href: string; label: string };

export function AdminShell({
  children,
  items = [],
  activeHref,
}: {
  children: ReactNode;
  items?: AdminItem[];
  activeHref?: string;
}) {
  return (
    <div className="admin-shell">
      <aside className="admin-aside">
        <nav aria-label="管理后台导航">
          {items.map((item) => (
            <Link key={item.href} className="admin-link" data-active={item.href === activeHref} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <section className="admin-content">{children}</section>
    </div>
  );
}
