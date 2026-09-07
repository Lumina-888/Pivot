"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "../../../components/ui/Button";
import { loginWithCredentials } from "../auth";

export function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    const result = await loginWithCredentials(username, password);
    setLoading(false);
    if (result.ok) {
      router.push(result.redirectTo);
      return;
    }
    setError(result.message);
  }

  return (
    <form className="frm" onSubmit={onSubmit}>
      <label htmlFor="username">用户名</label>
      <input
        id="username"
        name="username"
        autoComplete="username"
        value={username}
        onChange={(event) => setUsername(event.target.value)}
      />
      <div style={{ height: 12 }} />
      <label htmlFor="password">密码</label>
      <input
        id="password"
        name="password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      {error ? (
        <p className="user-error" role="alert">
          {error}
        </p>
      ) : (
        <p className="muted" style={{ marginTop: 8 }}>
          使用公司账号登录。失败时不会提示账号是否存在。
        </p>
      )}
      <div style={{ height: 18 }} />
      <Button type="submit" loading={loading} className="btn-primary" style={{ width: "100%" }}>
        登录
      </Button>
    </form>
  );
}
