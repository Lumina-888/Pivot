"use client";

import { type FormEvent, useEffect, useState } from "react";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Modal } from "../../../components/ui/Modal";
import { Table } from "../../../components/ui/Table";
import { errorMessage, isAdminForbidden } from "../rbac";
import { createAdminUser, disableUser, enableUser, listAdminUsers } from "../users";
import type { AdminUser, PageStatus } from "../types";
import { ForbiddenView } from "./ForbiddenView";
import { StatusBanner } from "./StatusBanner";

export function UsersView() {
  const [status, setStatus] = useState<PageStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function reload() {
    const list = await listAdminUsers();
    setUsers(list.items);
    setStatus(list.items.length ? "ready" : "empty");
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await reload();
      } catch (caught) {
        if (cancelled) {
          return;
        }
        if (isAdminForbidden(caught)) {
          setStatus("forbidden");
          return;
        }
        setError(errorMessage(caught, "无法加载用户"));
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "forbidden") {
    return <ForbiddenView />;
  }

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFeedback(null);
    try {
      const created = await createAdminUser({ username, initial_password: password });
      setCreateOpen(false);
      setUsername("");
      setPassword("");
      setFeedback(`已创建用户 ${created.username}`);
      await reload();
    } catch (caught) {
      if (isAdminForbidden(caught)) {
        setStatus("forbidden");
        return;
      }
      setError(errorMessage(caught, "创建用户失败"));
    }
  }

  async function onToggle(user: AdminUser) {
    setFeedback(null);
    try {
      const next =
        user.status === "active" ? await disableUser(user.user_id) : await enableUser(user.user_id);
      setFeedback(
        next.status === "disabled"
          ? `已停用 ${next.username}，其无法登录或访问受保护资源`
          : `已启用 ${next.username}`,
      );
      await reload();
    } catch (caught) {
      if (isAdminForbidden(caught)) {
        setStatus("forbidden");
        return;
      }
      setError(errorMessage(caught, "更新用户失败"));
    }
  }

  return (
    <div className="admin-page">
      <h1>用户管理</h1>
      <div className="admin-toolbar">
        <Button onClick={() => setCreateOpen(true)}>新建用户</Button>
      </div>
      {status === "loading" ? <StatusBanner tone="loading">正在加载用户…</StatusBanner> : null}
      {status === "error" ? <StatusBanner tone="error">{error ?? "无法加载用户"}</StatusBanner> : null}
      {status === "empty" ? <StatusBanner tone="empty">暂无用户</StatusBanner> : null}
      {feedback ? <StatusBanner tone="loading">{feedback}</StatusBanner> : null}
      {users.length ? (
        <Table caption="用户列表" headers={["用户名", "角色", "状态", "操作"]}>
          {users.map((user) => (
            <tr key={user.user_id}>
              <td>{user.username}</td>
              <td>{user.role}</td>
              <td>
                <Badge tone={user.status === "active" ? "green" : "gray"}>{user.status}</Badge>
              </td>
              <td>
                <Button variant={user.status === "active" ? "danger" : "ghost"} onClick={() => void onToggle(user)}>
                  {user.status === "active" ? "停用" : "启用"}
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      ) : null}
      <Modal open={createOpen} title="新建用户" onClose={() => setCreateOpen(false)}>
        <form className="admin-create" onSubmit={onCreate}>
          <label htmlFor="new-username">用户名</label>
          <input id="new-username" value={username} onChange={(event) => setUsername(event.target.value)} required />
          <label htmlFor="new-password">初始密码</label>
          <input
            id="new-password"
            type="password"
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          <p className="muted">契约仅接受 username 与 initial_password；角色变更走后续 PATCH。</p>
          <Button type="submit">创建</Button>
        </form>
      </Modal>
    </div>
  );
}
