export const ADMIN_NAV = [
  { href: "/admin", label: "概览" },
  { href: "/admin/docs", label: "文档管理" },
  { href: "/admin/users", label: "用户管理" },
  { href: "/admin/audit", label: "审计日志" },
] as const;

export function activeAdminHref(pathname: string): string {
  if (pathname.startsWith("/admin/docs")) {
    return "/admin/docs";
  }
  if (pathname.startsWith("/admin/users")) {
    return "/admin/users";
  }
  if (pathname.startsWith("/admin/audit")) {
    return "/admin/audit";
  }
  return "/admin";
}

export function buildAuditQuery(query: { actor?: string; action?: string }): string {
  const params = new URLSearchParams();
  const actor = query.actor?.trim();
  const action = query.action?.trim();
  if (actor) {
    params.set("actor", actor);
  }
  if (action) {
    params.set("action", action);
  }
  const encoded = params.toString();
  return encoded ? `/admin/audit-events?${encoded}` : "/admin/audit-events";
}
