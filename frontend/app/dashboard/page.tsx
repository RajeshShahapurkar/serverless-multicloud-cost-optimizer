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
  if (!user) redirect("/login");

  return (
    <main style={{ maxWidth: 1000, margin: "60px auto", padding: 24 }}>
      <h1>Multi-Cloud Cost Optimizer</h1>
      <p>Signed in as {user.email}</p>

      <h2 style={{ marginTop: 40 }}>Connect your cloud providers</h2>
      <p style={{ color: "#555" }}>
        Connect using provider authorization. You never paste cloud access keys into this application.
      </p>

      <div style={{ display: "grid", gap: 16, marginTop: 24 }}>
        {providers.map((provider) => (
          <section
            key={provider.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: 12,
              padding: 20,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div>
              <h3 style={{ margin: 0 }}>{provider.name}</h3>
              <p style={{ marginBottom: 0, color: "#666" }}>{provider.description}</p>
            </div>
            <a
              href={`/api/connect/${provider.id}`}
              style={{
                display: "inline-block",
                padding: "10px 18px",
                borderRadius: 8,
                background: "#111",
                color: "#fff",
                textDecoration: "none",
              }}
            >
              Connect
            </a>
          </section>
        ))}
      </div>
    </main>
  );
}
