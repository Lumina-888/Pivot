"use client";

import { type FormEvent, useEffect, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Table } from "../../../components/ui/Table";
import { canExpandAuditEvent, listAuditEvents, visibleAuditMetadata } from "../audit";
import { errorMessage, isAdminForbidden } from "../rbac";
import type { AuditEventInfo, PageStatus } from "../types";
import { ForbiddenView } from "./ForbiddenView";
import { StatusBanner } from "./StatusBanner";

export function AuditView() {
  const [status, setStatus] = useState<PageStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<AuditEventInfo[]>([]);
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  async function load(nextActor = actor, nextAction = action) {
    const list = await listAuditEvents({ actor: nextActor, action: nextAction });
    setEvents(list.items);
    setStatus(list.items.length ? "ready" : "empty");
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await load("", "");
      } catch (caught) {
        if (cancelled) {
          return;
        }
        if (isAdminForbidden(caught)) {
          setStatus("forbidden");
          return;
        }
        setError(errorMessage(caught, "无法加载审计"));
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
    // Initial load only; filters submit explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status === "forbidden") {
    return <ForbiddenView />;
  }

  async function onFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await load();
    } catch (caught) {
      if (isAdminForbidden(caught)) {
        setStatus("forbidden");
        return;
      }
      setError(errorMessage(caught, "无法加载审计"));
      setStatus("error");
    }
  }

  return (
    <div className="admin-page">
      <h1>审计日志</h1>
      <p className="muted">只读查询。事件不可修改或删除；敏感字段（Prompt/口令/思考链）不会在页面展示。</p>
      <form className="admin-toolbar" onSubmit={onFilter}>
        <div className="admin-filters">
          <input
            aria-label="按操作者筛选"
            placeholder="actor"
            value={actor}
            onChange={(event) => setActor(event.target.value)}
          />
          <input
            aria-label="按动作筛选"
            placeholder="action"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          />
          <Button type="submit">查询</Button>
        </div>
      </form>
      {status === "loading" ? <StatusBanner tone="loading">正在加载审计…</StatusBanner> : null}
      {status === "error" ? <StatusBanner tone="error">{error ?? "无法加载审计"}</StatusBanner> : null}
      {status === "empty" ? <StatusBanner tone="empty">暂无审计事件</StatusBanner> : null}
      {events.length ? (
        <Table caption="审计事件" headers={["时间", "操作者", "动作", "对象", "结果"]}>
          {events.flatMap((item) => {
            const rows = [
              <tr key={item.audit_event_id}>
                <td>{item.created_at}</td>
                <td>{item.actor}</td>
                <td>
                  {canExpandAuditEvent(item) ? (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() =>
                        setExpanded((current) => (current === item.audit_event_id ? null : item.audit_event_id))
                      }
                    >
                      {item.action}
                    </button>
                  ) : (
                    item.action
                  )}
                </td>
                <td>{item.target}</td>
                <td>{item.result}</td>
              </tr>,
            ];
            if (expanded === item.audit_event_id) {
              const visible = visibleAuditMetadata(item.metadata);
              rows.push(
                <tr key={`${item.audit_event_id}-expand`}>
                  <td colSpan={5} className="audit-expand">
                    <div>run_id：{item.run_id ?? "—"}</div>
                    <div>request_id：{item.request_id ?? "—"}</div>
                    <pre>{JSON.stringify(visible, null, 2)}</pre>
                  </td>
                </tr>,
              );
            }
            return rows;
          })}
        </Table>
      ) : null}
    </div>
  );
}
