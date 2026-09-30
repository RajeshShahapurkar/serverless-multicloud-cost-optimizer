import { redirect } from "next/navigation";
import { createClient } from "../../lib/supabase/server";

const providers = [
  { id: "aws", name: "AWS", description: "Read-only cloud resources and cost data" },
  { id: "gcp", name: "Google Cloud", description: "Read-only cloud resources and billing data" },
  { id: "azure", name: "Microsoft Azure", description: "Read-only resources and billing data" },
];

export default async function Dashboard() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const { data: { session } } = await supabase.auth.getSession();
  if (!user || !session) redirect("/login");

  const { data: accounts } = await supabase.from("cloud_accounts")
    .select("provider,status,display_name,account_identifier,last_synced_at,error_message")
    .eq("user_id", user.id);
  const accountMap = new Map((accounts ?? []).map((a) => [a.provider, a]));

  const gcpAccount = accountMap.get("gcp");

  let gcpBilling: {
    status: string;
    billing_accounts: number;
    message: string;
  } | null = null;

  if (gcpAccount) {
    try {
      const response = await fetch(
        (process.env.BACKEND_URL ?? "http://localhost:8000") +
          "/api/providers/gcp/billing-status",
        {
          headers: { Authorization: "Bearer " + session.access_token },
          cache: "no-store",
        },
      );
      if (response.ok) {
        gcpBilling = await response.json();
      }
    } catch {
      gcpBilling = null;
    }
  }
  const { data: resources } = gcpAccount
    ? await supabase.from("cloud_resources")
        .select("resource_type,resource_name,region,status,metadata")
        .eq("user_id", user.id)
        .eq("cloud_account_id", (await supabase.from("cloud_accounts").select("id").eq("user_id", user.id).eq("provider", "gcp").single()).data?.id ?? "")
        .order("resource_type")
        .order("resource_name")
    : { data: [] };

  return (
    <main style={{ maxWidth: 1000, margin: "60px auto", padding: 24 }}>
      <h1>Multi-Cloud Cost Optimizer</h1>
      <p>Signed in as {user.email}</p>

      <h2 style={{ marginTop: 40 }}>Connect your cloud providers</h2>
      <p style={{ color: "#555" }}>
        Connect using provider authorization. You never paste cloud access keys into this application.
      </p>

      <div style={{ display: "grid", gap: 16, marginTop: 24 }}>
        {providers.map((provider) => {
          const account = accountMap.get(provider.id);
          const connected = account?.status === "connected";
          return (
            <section key={provider.id} style={{
              border: "1px solid #ddd", borderRadius: 12, padding: 20,
              display: "flex", alignItems: "center", justifyContent: "space-between"
            }}>
              <div>
                <h3 style={{ margin: 0 }}>{provider.name}</h3>
                <p style={{ marginBottom: 4, color: "#666" }}>{provider.description}</p>
                {connected && <small>✓ Connected{account?.account_identifier ? " · " + account.account_identifier : ""}</small>}
                {account?.error_message && <small style={{ display: "block", color: "#a33", marginTop: 6 }}>{account.error_message}</small>}
              </div>
              {provider.id === "gcp" ? (
                <div style={{ display: "flex", gap: 8 }}>
                  <a href="/api/providers/gcp/connect" style={{
                    display: "inline-block", padding: "10px 18px", borderRadius: 8,
                    background: "#111", color: "#fff", textDecoration: "none"
                  }}>
                    {connected ? "Reconnect" : "Connect"}
                  </a>
                  {connected && (
                    <a href="/api/providers/gcp/sync" style={{
                      display: "inline-block", padding: "10px 18px", borderRadius: 8,
                      border: "1px solid #111", color: "#111", textDecoration: "none"
                    }}>
                      Sync resources
                    </a>
                  )}
                </div>
              ) : (
                <span style={{ color: "#777" }}>Coming soon</span>
              )}
            </section>
          );
        })}
      </div>

      {gcpAccount?.status === "connected" && (
        <>
          <section style={{
            marginTop: 40,
            border: "1px solid #ddd",
            borderRadius: 12,
            padding: 20,
          }}>
            <h2 style={{ marginTop: 0 }}>Google Cloud Billing</h2>
            {gcpBilling ? (
              <>
                <p style={{ marginBottom: 6 }}>
                  Status: <strong>{gcpBilling.status}</strong>
                </p>
                <p style={{ color: "#666", marginTop: 0 }}>
                  {gcpBilling.message}
                </p>
                {gcpBilling.status === "available" && (
                  <p style={{ marginBottom: 0 }}>
                    Billing accounts visible: {gcpBilling.billing_accounts}
                  </p>
                )}
              </>
            ) : (
              <p style={{ color: "#666" }}>
                Billing status could not be checked right now.
              </p>
            )}
          </section>

          <section style={{ marginTop: 40 }}>
          <h2>Google Cloud Resource Inventory</h2>
          <p style={{ color: "#666" }}>
            {resources?.length ?? 0} resources stored from the latest synchronization.
          </p>
          {resources && resources.length > 0 ? (
            <div style={{ overflowX: "auto", border: "1px solid #ddd", borderRadius: 12 }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: 12 }}>Type</th>
                    <th style={{ textAlign: "left", padding: 12 }}>Name</th>
                    <th style={{ textAlign: "left", padding: 12 }}>Region / Zone</th>
                    <th style={{ textAlign: "left", padding: 12 }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {resources.map((resource, index) => (
                    <tr key={resource.resource_type + ":" + resource.resource_name + ":" + index}>
                      <td style={{ padding: 12 }}>{resource.resource_type}</td>
                      <td style={{ padding: 12 }}>{resource.resource_name}</td>
                      <td style={{ padding: 12 }}>{resource.region || "—"}</td>
                      <td style={{ padding: 12 }}>{resource.status || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>No resources have been synchronized yet. Click <strong>Sync resources</strong>.</p>
          )}
          </section>
        </>
      )}
    </main>
  );
}
