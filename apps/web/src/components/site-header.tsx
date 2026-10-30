"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiMode, getMode } from "@/lib/api";

export function SiteHeader() {
  const pathname = usePathname();
  const [mode, setMode] = useState<ApiMode | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    getMode().then(setMode).catch(() => setOffline(true));
  }, []);

  const links = [
    { href: "/concierge", label: "Concierge" },
    { href: "/developers", label: "Developers" },
  ];

  return (
    <header className="site-header">
      <Link className="wordmark" href="/" aria-label="TasteOS home">
        TasteOS
      </Link>
      <nav aria-label="Primary navigation">
        {links.map((link) => (
          <Link
            key={link.href}
            className={pathname.startsWith(link.href) ? "active" : ""}
            href={link.href}
          >
            {link.label}
          </Link>
        ))}
      </nav>
      <div
        className={`mode-badge ${offline ? "offline" : ""} ${mode?.mode === "live" ? "live" : ""}`}
        title={mode?.description}
        aria-live="polite"
      >
        <span aria-hidden="true" />
        {offline
          ? "API offline"
          : mode
            ? mode.mode === "demo"
              ? "Demo mode"
              : "Live mode"
            : "Checking mode"}
      </div>
    </header>
  );
}
