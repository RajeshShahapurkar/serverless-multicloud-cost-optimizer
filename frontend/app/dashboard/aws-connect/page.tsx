"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type Setup = {
  external_id: string;
  trusted_principal_arn: string;
  instructions: string;
};

export default function AWSConnectPage() {
  const router = useRouter();
  const [setup, setSetup] = useState<Setup | null>(null);
  const [roleArn, setRoleArn] = useState("");
  const [region, setRegion] = useState("us-east-1");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    setMessage("");
    const response = await fetch("/api/providers/aws/connect/start", { method: "POST" });
    const body = await response.json();
    if (!response.ok) setMessage(body.detail || body.error || "Could not start AWS setup.");
    else setSetup(body);
    setBusy(false);
  }

  async function complete() {
    setBusy(true);
    setMessage("");
    const response = await fetch("/api/providers/aws/connect/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role_arn: roleArn, region }),
    });
    const body = await response.json();
    if (!response.ok) setMessage(body.detail || body.error || "AWS role verification failed.");
    else {
      setMessage("AWS account connected successfully.");
      setTimeout(() => router.push("/dashboard"), 700);
    }
    setBusy(false);
  }

  return (
    <main style={{ maxWidth: 900, margin: "50px auto", padding: 24 }}>
      <h1>Connect an AWS account</h1>
      <p style={{ color: "#555" }}>
        This uses a cross-account IAM role and temporary STS credentials. Do not enter an AWS access key or secret key here.
      </p>

      {!setup ? (
        <button onClick={start} disabled={busy} style={{ padding: "10px 18px" }}>
          {busy ? "Preparing..." : "Start AWS connection"}
        </button>
      ) : (
        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 20 }}>
          <h2>1. Create the IAM role in your AWS account</h2>
          <p>{setup.instructions}</p>
          <p><strong>Trusted principal:</strong> {setup.trusted_principal_arn}</p>
          <p><strong>External ID:</strong> {setup.external_id}</p>

          <h2>2. Enter the role ARN</h2>
          <input
            value={roleArn}
            onChange={(e) => setRoleArn(e.target.value)}
            placeholder="arn:aws:iam::123456789012:role/CostOptimizerReadOnly"
            style={{ width: "100%", padding: 10, boxSizing: "border-box" }}
          />

          <label style={{ display: "block", marginTop: 14 }}>
            AWS region
            <select value={region} onChange={(e) => setRegion(e.target.value)} style={{ display: "block", padding: 8, marginTop: 6 }}>
              <option>us-east-1</option>
              <option>us-west-2</option>
              <option>ap-south-1</option>
              <option>eu-west-1</option>
            </select>
          </label>

          <button onClick={complete} disabled={busy || !roleArn.trim()} style={{ marginTop: 18, padding: "10px 18px" }}>
            {busy ? "Verifying..." : "Verify and connect"}
          </button>
          <button onClick={() => router.push("/dashboard")} style={{ marginLeft: 10, padding: "10px 18px" }}>
            Cancel
          </button>

          {message && <p style={{ marginTop: 16 }}>{message}</p>}
        </section>
      )}
    </main>
  );
}
