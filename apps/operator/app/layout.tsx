import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
  title: "IronTrust Operator Console",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // data-theme is set once, statically, per app (FE-3) — it is the operator
  // skin selector, never a runtime-toggled user preference.
  return (
    <html lang="en" data-theme="operator">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
