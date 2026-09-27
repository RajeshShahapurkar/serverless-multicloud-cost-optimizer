import Link from "next/link";

export default function Home() {
  return <main style={{maxWidth:900,margin:"80px auto",padding:24,fontFamily:"Arial"}}>
    <h1>Serverless Multi-Cloud Cost Optimizer</h1>
    <p>Monitor AWS, GCP and Azure spend from one place.</p>
    <p><Link href="/login">Login</Link> · <Link href="/register">Create account</Link></p>
  </main>;
}