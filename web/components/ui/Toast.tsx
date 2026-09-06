"use client";

import { type ReactNode, useEffect, useRef } from "react";

export function Toast({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean;
  title?: string;
  children: ReactNode;
  onClose?: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      ref.current?.focus();
    }
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div ref={ref} className="toast" role="status" aria-live="polite" tabIndex={-1} onClick={onClose}>
      {title ? <strong>{title}</strong> : null}
      {children}
    </div>
  );
}
