import { NextResponse } from "next/server";
import { createClient } from "../../../../../../lib/supabase/server";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST() {
  const supabase = await createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

  const response = await fetch(backendUrl + "/api/providers/aws/connect/start", {
    method: "POST",
    headers: { Authorization: "Bearer " + session.access_token },
    cache: "no-store",
  });
  const body = await response.json();
  return NextResponse.json(body, { status: response.status });
}
