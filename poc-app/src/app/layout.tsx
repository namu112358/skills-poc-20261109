import type { ReactNode } from "react";

export const metadata = { title: "PoC タスク管理" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 24 }}>{children}</body>
    </html>
  );
}
