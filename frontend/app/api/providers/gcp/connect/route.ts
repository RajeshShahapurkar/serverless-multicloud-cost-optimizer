import { NextResponse } from "next/server";
import { createClient } from "../../../../../lib/supabase/server";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export async function GET() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const { data: { session } } = await supabase.auth.getSession();

  if (!user || !session) {
    return NextResponse.redirect(new URL("/login", siteUrl));
  }

  const response = await fetch(backendUrl + "/api/providers/gcp/connect", {
    method: "POST",
    headers: { Authorization: "Bearer " + session.access_token },
    cache: "no-store",
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/dashboard?cloud_error=gcp_connect_start_failed", siteUrl)
    );
  }

  const data = await response.json();
  return NextResponse.redirect(data.authorization_url);
}
