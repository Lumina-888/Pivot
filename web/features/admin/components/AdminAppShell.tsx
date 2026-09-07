"use client";

import { type ReactNode, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AdminShell } from "../../../components/layouts/AdminShell";
import { Topbar } from "../../../components/layouts/Topbar";
import { getAccessToken, logout, refresh } from "../../../lib/auth/session";
import { ADMIN_NAV, activeAdminHref } from "../routes";

export function AdminAppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (getAccessToken()) {
        if (!cancelled) {
          setReady(true);
        }
        return;
      }
      try {
        await refresh();
        if (!cancelled) {
          setReady(true);
        }
      } catch {
        router.replace("/login");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!ready) {
    return (
      <p className="status-banner" data-tone="loading" role="status">
        正在验证会话…
      </p>
    );
  }

  return (
    <>
      <Topbar
        nav={[
          { href: "/", label: "首页" },
          { href: "/library", label: "知识库" },
          { href: "/chat", label: "对话" },
        ]}
        activeHref="/admin"
      >
        <button
          type="button"
          className="user-btn"
          onClick={async () => {
            await logout();
            router.replace("/login");
          }}
        >
          退出登录
        </button>
      </Topbar>
      <AdminShell items={[...ADMIN_NAV]} activeHref={activeAdminHref(pathname)}>
        {children}
      </AdminShell>
    </>
  );
}
