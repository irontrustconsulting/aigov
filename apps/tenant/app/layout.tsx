import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "./providers";
import { TenantSidebar } from "./_components/tenant-sidebar";
import { TopUtilityBar } from "./_components/top-utility-bar";
import { AppShell } from "@irontrust/ui";

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
          <AppShell sidebar={<TenantSidebar />}>
            <div className="flex h-full flex-col">
              <TopUtilityBar />
              <div className="flex-1 overflow-y-auto">{children}</div>
            </div>
          </AppShell>
        </Providers>
      </body>
    </html>
  );
}
