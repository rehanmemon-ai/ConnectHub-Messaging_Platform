import { useState } from "react";

import { Button, Field } from "../../components/ui/primitives";
import { Icon } from "../../components/ui/Icon";
import { errorMessage, fieldErrors } from "../../lib/api";
import { useAuth } from "../../app/AuthContext";
import { Link, navigate } from "../../app/router";

function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return <main className="auth-layout"><section className="auth-story"><div className="auth-brand"><span className="brand-mark"><Icon name="chat"/></span>ConnectHub</div><div><p className="eyebrow">Make space for better conversation</p><h1>Where your communities come alive.</h1><p>Focused rooms, real-time connection, and intelligent search—all in one calm workspace.</p></div><div className="auth-proof"><div className="avatar-stack"><span>RK</span><span>AM</span><span>JL</span></div><p>Built for teams, study groups, and communities that value clarity.</p></div></section><section className="auth-panel"><div className="auth-card"><div className="auth-mobile-brand"><Icon name="chat"/> ConnectHub</div><h2>{title}</h2><p className="auth-subtitle">{subtitle}</p>{children}</div></section></main>;
}

function PasswordInput({
  autoComplete,
  id,
  label,
  onChange,
  value,
}: {
  autoComplete: "current-password" | "new-password";
  id: string;
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  const [visible, setVisible] = useState(false);
  return <span className="password-input"><input autoComplete={autoComplete} id={id} onChange={(event) => onChange(event.target.value)} type={visible ? "text" : "password"} value={value}/><button aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`} aria-pressed={visible} onClick={() => setVisible((current) => !current)} type="button">{visible ? "Hide" : "Show"}</button></span>;
}

export function LoginPage() {
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState(""); const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const notice = new URLSearchParams(window.location.search).get("registered");
  async function submit(event: React.FormEvent) { event.preventDefault(); setError(""); if (!identifier.trim() || !password) { setError("Enter your username or email and password."); return; } setBusy(true); try { await login(identifier, password); navigate("/app", { replace: true }); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } }
  return <AuthFrame title="Welcome back" subtitle="Sign in to continue to your conversations.">{notice ? <div className="notice notice-success" role="status"><Icon name="check"/> Account created. Sign in to get started.</div> : null}<form className="form-stack" onSubmit={submit}><Field label="Username or email"><input autoComplete="username" onChange={(e) => setIdentifier(e.target.value)} value={identifier}/></Field><Field controlId="login-password" label="Password"><PasswordInput autoComplete="current-password" id="login-password" label="Password" onChange={setPassword} value={password}/></Field>{error ? <div className="notice notice-error" role="alert">{error}</div> : null}<Button busy={busy} type="submit">Sign in</Button></form><p className="auth-switch">New to ConnectHub? <Link to="/register">Create an account</Link></p></AuthFrame>;
}

export function RegisterPage() {
  const { register } = useAuth();
  const [form, setForm] = useState({ username: "", email: "", display_name: "", password: "", confirm: "" });
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [errors, setErrors] = useState<Record<string, string>>({});
  function change(key: keyof typeof form, value: string) { setForm((current) => ({ ...current, [key]: value })); }
  async function submit(event: React.FormEvent) { event.preventDefault(); setError(""); const local: Record<string, string> = {}; if (!form.username.trim() || /\s/.test(form.username)) local.username = "Use 1–50 characters without spaces."; if (!form.email.includes("@")) local.email = "Enter a valid email address."; if (!form.display_name.trim()) local.display_name = "Enter your display name."; if (form.password.length < 12) local.password = "Use at least 12 characters."; if (form.password !== form.confirm) local.confirm = "Passwords do not match."; setErrors(local); if (Object.keys(local).length) return; setBusy(true); try { await register({ username: form.username, email: form.email, display_name: form.display_name, password: form.password }); setForm((current) => ({ ...current, password: "", confirm: "" })); navigate("/login?registered=1", { replace: true }); } catch (reason) { setErrors(fieldErrors(reason)); setError(errorMessage(reason)); } finally { setBusy(false); } }
  return <AuthFrame title="Create your account" subtitle="Start a room, join a community, and stay in the loop."><form className="form-stack" onSubmit={submit}><div className="form-grid"><Field error={errors.display_name} label="Display name"><input autoComplete="name" onChange={(e) => change("display_name", e.target.value)} value={form.display_name}/></Field><Field error={errors.username} label="Username"><input autoComplete="username" onChange={(e) => change("username", e.target.value)} value={form.username}/></Field></div><Field error={errors.email} label="Email"><input autoComplete="email" onChange={(e) => change("email", e.target.value)} type="email" value={form.email}/></Field><Field controlId="register-password" error={errors.password} hint="At least 12 characters" label="Password"><PasswordInput autoComplete="new-password" id="register-password" label="Password" onChange={(value) => change("password", value)} value={form.password}/></Field><Field controlId="register-password-confirm" error={errors.confirm} label="Confirm password"><PasswordInput autoComplete="new-password" id="register-password-confirm" label="Confirm password" onChange={(value) => change("confirm", value)} value={form.confirm}/></Field>{error ? <div className="notice notice-error" role="alert">{error}</div> : null}<Button busy={busy} type="submit">Create account</Button></form><p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p></AuthFrame>;
}
