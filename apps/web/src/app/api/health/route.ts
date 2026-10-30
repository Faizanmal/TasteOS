import { NextResponse } from "next/server";

/** Lightweight frontend health endpoint for local ops / load balancers. */
export async function GET() {
  return NextResponse.json({
    status: "ok",
    service: "tasteos-web",
    api_base_url: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
  });
}
