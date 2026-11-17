import { useState } from "react";

import { useAuth } from "../../app/AuthContext";
import { useToast } from "../../app/ToastContext";
import { Avatar, Button, Field } from "../../components/ui/primitives";
import { errorMessage } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

export function ProfilePage() {
  const { user, updateProfile } = useAuth(); const toast = useToast();
  const [username, setUsername] = useState(user?.username ?? ""); const [displayName, setDisplayName] = useState(user?.display_name ?? ""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: React.FormEvent) { event.preventDefault(); setError(""); if (!username.trim() || /\s/.test(username)) { setError("Username must be 1–50 characters without whitespace."); return; } if (!displayName.trim()) { setError("Display name is required."); return; } setBusy(true); try { await updateProfile({ username, display_name: displayName }); toast("Profile updated.", "success"); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } }
  if (!user) return null;
  return <div className="page-stack narrow-page"><div className="page-heading"><div><p className="eyebrow">Personal settings</p><h1>Your profile</h1><p>Control how people recognize you across ConnectHub.</p></div></div><section className="profile-hero"><Avatar name={user.display_name} size="lg"/><div><h2>{user.display_name}</h2><p>@{user.username}</p><small>Member since {formatDateTime(user.created_at)}</small></div></section><section className="section-card"><form className="form-stack" onSubmit={submit}><div className="form-grid"><Field label="Display name"><input maxLength={100} onChange={(e) => setDisplayName(e.target.value)} value={displayName}/></Field><Field label="Username"><input maxLength={50} onChange={(e) => setUsername(e.target.value)} value={username}/></Field></div><Field hint="Email changes are not supported in the current account model." label="Email"><input disabled readOnly value={user.email}/></Field>{error ? <div className="notice notice-error" role="alert">{error}</div> : null}<div><Button busy={busy} type="submit">Save changes</Button></div></form></section></div>;
}
