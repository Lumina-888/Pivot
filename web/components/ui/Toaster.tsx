"use client";

import type { ReactNode } from "react";

export function Toaster({ children }: { children?: ReactNode }) {
  return (
    <div className="toaster" aria-live="polite" aria-atomic="true">
      {children}
    </div>
  );
}
