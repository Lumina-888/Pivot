"use client";

import { type ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Page } from "../../../components/layouts/Page";
import { getAccessToken, refresh } from "../../../lib/auth/session";

export function SessionGate({ children }: { children: ReactNode }) {
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
      <Page>
        <StatusPending />
      </Page>
    );
  }
  return children;
}

function StatusPending() {
  return (
    <p className="status-banner" data-tone="loading" role="status">
      正在验证会话…
    </p>
  );
}
