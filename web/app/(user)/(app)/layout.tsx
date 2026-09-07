import type { ReactNode } from "react";
import { UserShell } from "../../../features/user/components/UserShell";

export default function UserAppLayout({ children }: { children: ReactNode }) {
  return <UserShell>{children}</UserShell>;
}
