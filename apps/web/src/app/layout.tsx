import type { Metadata } from "next";
import { Cormorant_Garamond, Manrope } from "next/font/google";
import { SiteHeader } from "@/components/site-header";
import { cn } from "@/lib/utils";
import "./globals.css";

const display = Cormorant_Garamond({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const sans = Manrope({
  variable: "--font-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "TasteOS — Cultural Intelligence",
    template: "%s · TasteOS",
  },
  description: "The Cultural Intelligence Layer for AI Agents.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={cn(display.variable, sans.variable, "font-sans")}>
      <body>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
