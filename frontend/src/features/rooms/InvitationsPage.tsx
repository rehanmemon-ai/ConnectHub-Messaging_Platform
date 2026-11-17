import { api, errorMessage } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import type { Invitation, Page } from "../../types/api";
import { Button, EmptyState, Skeleton } from "../../components/ui/primitives";
import { Icon } from "../../components/ui/Icon";
import { useToast } from "../../app/ToastContext";
import { navigate } from "../../app/router";

export function InvitationsPage() {
  const toast = useToast();
  const invitations = useAsync((signal) => api<Page<Invitation>>("/api/v1/users/me/invitations?limit=50", { signal }), []);
  async function respond(invitation: Invitation, action: "accept" | "decline") { try { await api(`/api/v1/invitations/${invitation.id}/${action}`, { method: "POST" }); toast(action === "accept" ? `Welcome to ${invitation.room_name}.` : "Invitation declined.", "success"); invitations.reload(); if (action === "accept") navigate(`/app/rooms/${invitation.room_id}`); } catch (reason) { toast(errorMessage(reason), "error"); invitations.reload(); } }
  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Private spaces</p><h1>Invitations</h1><p>Review rooms that people have invited you to join.</p></div></div><section className="section-card">{invitations.loading ? <Skeleton lines={4}/> : invitations.error ? <div className="inline-error">{errorMessage(invitations.error)} <button onClick={invitations.reload}>Retry</button></div> : invitations.data?.items.length ? <div className="invitation-list">{invitations.data.items.map((invitation) => <article className="invitation-card" key={invitation.id}><span className="room-icon"><Icon name="mail"/></span><div><h3>{invitation.room_name}</h3><p><strong>@{invitation.inviter_username}</strong> invited you to a private room.</p><small>Expires {formatDateTime(invitation.expires_at)}</small></div><div className="invitation-actions"><Button onClick={() => respond(invitation, "accept")}>Accept</Button><Button onClick={() => respond(invitation, "decline")} variant="ghost">Decline</Button></div></article>)}</div> : <EmptyState icon="mail" title="No pending invitations" description="New private-room invitations will appear here."/>}</section></div>;
}
