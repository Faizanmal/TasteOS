import Link from "next/link";
import { ApiStatus } from "@/components/api-status";
import { ModeBanner } from "@/components/mode-banner";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function Home() {
  return (
    <main className="hero">
      <div className="hero-content">
        <ModeBanner />
        <div className="eyebrow">Cultural intelligence, made actionable</div>
        <div className="hero-brand" aria-label="TasteOS">
          TasteOS
        </div>
        <h1>The Cultural Intelligence Layer for AI Agents.</h1>
        <p>
          Turn a roomful of different tastes into one considered plan—without
          flattening what makes each person distinct. Group Concierge shows the
          evidence, the trade-offs, and the proposed outing.
        </p>
        <div className="actions">
          <Link
            href="/concierge"
            className={cn(
              buttonVariants({ variant: "default", size: "lg" }),
              "h-12 rounded-none bg-[color:var(--ink)] px-5 text-[0.78rem] font-bold tracking-[0.07em] uppercase hover:bg-[color:var(--copper)]",
            )}
          >
            Plan for a group <span aria-hidden="true">→</span>
          </Link>
          <Link
            href="/developers"
            className={cn(
              buttonVariants({ variant: "outline", size: "lg" }),
              "h-12 rounded-none border-[color:var(--ink)] bg-transparent px-5 text-[0.78rem] font-bold tracking-[0.07em] uppercase text-[color:var(--ink)] hover:bg-[color:var(--copper)] hover:text-white",
            )}
          >
            Explore the API
          </Link>
        </div>
        <div className="mt-10 max-w-xl">
          <ApiStatus />
        </div>
      </div>
    </main>
  );
}
