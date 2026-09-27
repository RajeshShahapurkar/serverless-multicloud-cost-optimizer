import { redirect } from "next/navigation";
import { createClient } from "../../lib/supabase/server";

export default async function Dashboard() {
  const supabase=await createClient();
  const {data:{user}}=await supabase.auth.getUser();
  if(!user) redirect("/login");
  return <main style={{maxWidth:1000,margin:"60px auto",padding:24}}>
    <h1>Dashboard</h1>
    <p>Signed in as {user.email}</p>
    <h2>Cloud connections</h2>
    <p>AWS, GCP and Azure connection management is the next implementation slice.</p>
  </main>;
}