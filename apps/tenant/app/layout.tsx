import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "./providers";
import { AppNav } from "./_components/app-nav";

export const metadata = {
  title: "IronTrust",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // data-theme is set once, statically, per app (FE-3) — it is the tenant
  // skin selector, never a runtime-toggled user preference.
  return (
    <html lang="en" data-theme="tenant">
      <body>
        <Providers>
          <AppNav />
          {children}
        </Providers>
      </body>
    </html>
  );
}
