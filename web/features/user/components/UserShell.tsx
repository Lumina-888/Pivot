"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Topbar } from "../../../components/layouts/Topbar";
import { logout } from "../../../lib/auth/session";
import { USER_NAV, searchPageHref } from "../routes";
import { SessionGate } from "./SessionGate";

export function UserShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const activeHref = pathname.startsWith("/library")
    ? "/library"
    : pathname.startsWith("/chat")
      ? "/chat"
      : pathname.startsWith("/search")
        ? "/library"
        : pathname;

  return (
    <SessionGate>
      <Topbar
        nav={[...USER_NAV]}
        activeHref={activeHref}
        onSearch={(query) => {
          router.push(searchPageHref(query));
        }}
      >
        <Link href="/admin" className="sr-only">
          管理后台
        </Link>
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
      {children}
    </SessionGate>
  );
}
