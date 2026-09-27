"use client";

import { FormEvent, useState } from "react";
import { createClient } from "../../lib/supabase/browser";
import Link from "next/link";

export default function LoginPage() {
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [message,setMessage]=useState("");
  async function submit(e:FormEvent) {
    e.preventDefault();
    const {error}=await createClient().auth.signInWithPassword({email,password});
    if(error) return setMessage(error.message);
    window.location.href="/dashboard";
  }
  return <main style={{maxWidth:420,margin:"80px auto",padding:24}}>
    <h1>Login</h1>
    <form onSubmit={submit} style={{display:"grid",gap:12}}>
      <input required type="email" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)}/>
      <input required type="password" placeholder="Password" value={password} onChange={e=>setPassword(e.target.value)}/>
      <button type="submit">Login</button>
    </form>
    {message && <p>{message}</p>}
    <Link href="/register">Create account</Link>
  </main>;
}