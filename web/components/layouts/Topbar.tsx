"use client";

import Link from "next/link";
import { type FormEvent, type ReactNode, useEffect, useRef } from "react";
import { cn } from "../../lib/cn";

type NavItem = { href: string; label: string };

export function Topbar({
  nav = [],
  activeHref,
  user,
  onSearch,
  children,
}: {
  nav?: NavItem[];
  activeHref?: string;
  user?: ReactNode;
  onSearch?: (query: string) => void;
  children?: ReactNode;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch?.(inputRef.current?.value.trim() ?? "");
  }

  return (
    <header className="topbar">
      <Link className="logo" href="/" aria-label="问枢 Pivot 首页">
        <span className="logo-mark" aria-hidden="true">
          枢
        </span>
        问枢 <small>Pivot</small>
      </Link>
      <nav className="nav" aria-label="主导航">
        {nav.map((item) => (
          <Link
            key={item.href}
            className={cn("nav-link")}
            data-active={item.href === activeHref}
            href={item.href}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <form className="global-search" onSubmit={submit} role="search">
        <label className="sr-only" htmlFor="global-query">
          搜索文档或问 AI
        </label>
        <span aria-hidden="true">⌕</span>
        <input ref={inputRef} id="global-query" placeholder="搜索文档 / 问 AI…" autoComplete="off" />
        <kbd>Ctrl K</kbd>
      </form>
      {children ?? user}
    </header>
  );
}
