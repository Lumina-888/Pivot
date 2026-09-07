"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Table } from "../../../components/ui/Table";
import { getAdminMetrics, metricEntries } from "../metrics";
import { errorMessage, isAdminForbidden } from "../rbac";
import { listAdminTasks } from "../tasks";
import type { AdminTaskInfo, PageStatus } from "../types";
import { ForbiddenView } from "./ForbiddenView";
import { StatusBanner } from "./StatusBanner";

export function OverviewView() {
  const [status, setStatus] = useState<PageStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const [tasks, setTasks] = useState<AdminTaskInfo[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [metricPayload, taskList] = await Promise.all([getAdminMetrics(), listAdminTasks()]);
        if (cancelled) {
          return;
        }
        setMetrics(metricPayload);
        setTasks(taskList.items);
        setStatus(taskList.items.length || Object.keys(metricPayload).length ? "ready" : "empty");
      } catch (caught) {
        if (cancelled) {
          return;
        }
        if (isAdminForbidden(caught)) {
          setStatus("forbidden");
          return;
        }
        setError(errorMessage(caught, "无法加载概览"));
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

  const entries = metricEntries(metrics);

  return (
    <div className="admin-page">
      <h1>后台概览</h1>
      <p className="muted">运行指标字段尚未冻结（TBD-P0）；此处按服务端返回的键值展示，不承诺具体字段名。</p>
      {status === "loading" ? <StatusBanner tone="loading">正在加载概览…</StatusBanner> : null}
      {status === "error" ? <StatusBanner tone="error">{error ?? "无法加载概览"}</StatusBanner> : null}
      <div className="statgrid">
        <Link className="stat" href="/admin/docs">
          <div className="sk">文档管理</div>
          <div className="sv">进入</div>
        </Link>
        <Link className="stat" href="/admin/users">
          <div className="sk">用户管理</div>
          <div className="sv">进入</div>
        </Link>
        <Link className="stat" href="/admin/audit">
          <div className="sk">审计日志</div>
          <div className="sv">只读</div>
        </Link>
      </div>
      {entries.length ? (
        <Table caption="未冻结运行指标" headers={["键", "值"]}>
          {entries.map(([key, value]) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{value}</td>
            </tr>
          ))}
        </Table>
      ) : null}
      <h2 style={{ marginTop: 24 }}>解析任务</h2>
      {status === "empty" ? <StatusBanner tone="empty">暂无任务</StatusBanner> : null}
      {tasks.length ? (
        <Table caption="解析任务" headers={["任务", "实体", "状态", "可重试"]}>
          {tasks.map((task) => (
            <tr key={task.task_id}>
              <td>{task.task_id}</td>
              <td>
                {task.entity_type} / {task.entity_id}
              </td>
              <td>{task.state}</td>
              <td>{task.retryable ? "是" : "否"}</td>
            </tr>
          ))}
        </Table>
      ) : null}
    </div>
  );
}
