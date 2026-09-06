import type { Metadata } from "next";
import { Toaster } from "../components/ui/Toaster";
import "./globals.css";

export const metadata: Metadata = {
  title: "问枢 Pivot",
  description: "企业文档智能问答系统",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
