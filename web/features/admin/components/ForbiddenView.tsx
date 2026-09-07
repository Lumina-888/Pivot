import { StatusBanner } from "./StatusBanner";

export function ForbiddenView() {
  return (
    <div className="admin-page">
      <h1>管理后台</h1>
      <StatusBanner tone="forbidden">无权限访问管理后台。普通用户请求 /api/v1/admin/* 由服务端返回 AUTH_FORBIDDEN。</StatusBanner>
    </div>
  );
}
