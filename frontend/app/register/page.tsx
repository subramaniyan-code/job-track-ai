"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, fullName, password);
    } catch (err: any) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="h-12 w-12 rounded-2xl bg-brand-600 flex items-center justify-center text-white font-bold text-lg mb-3">JT</div>
          <h1 className="text-xl font-bold">Create your account</h1>
          <p className="text-sm text-slate-500 text-center">The email set as super admin in the server config gets full admin access automatically</p>
        </div>

        <form onSubmit={handleSubmit} className="card p-6 space-y-4">
          {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-100 rounded-lg px-3 py-2">{error}</div>}
          <div>
            <label className="label">Full name</label>
            <input className="input" required value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your name" />
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div>
            <label className="label">Password</label>
            <input className="input" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
          </div>
          <button type="submit" disabled={loading} className="btn btn-primary w-full">
            {loading ? "Creating account\u2026" : "Create account"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500 mt-5">
          Already have an account? <Link href="/login" className="text-brand-600 font-semibold">Log in</Link>
        </p>
      </div>
    </div>
  );
}
