import { NextResponse } from "next/server";
import { createClient } from "../../../../../../lib/supabase/server";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: Request) {
  const supabase = await createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

  const payload = await request.json();
  const response = await fetch(backendUrl + "/api/providers/aws/connect/complete", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + session.access_token,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await response.json();
  return NextResponse.json(body, { status: response.status });
}
