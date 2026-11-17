import { useState } from "react";

import { api, errorMessage } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import type { Notification, Page } from "../../types/api";
import { Button, EmptyState, Skeleton } from "../../components/ui/primitives";
import { Icon } from "../../components/ui/Icon";
import { navigate } from "../../app/router";
import { useToast } from "../../app/ToastContext";

function copy(notification: Notification): { title: string; text: string; icon: "mail" | "user" | "chat" } {
  if (notification.type === "room_invitation") return { title: "New room invitation", text: "Someone invited you to a private conversation.", icon: "mail" };
  if (notification.type === "room_membership_removed") return { title: "Room access changed", text: "An owner removed your membership from a room.", icon: "user" };
  return { title: "You were mentioned", text: "A room member mentioned you in a message.", icon: "chat" };
}

export function NotificationsPage() {
  const toast = useToast(); const [cursor, setCursor] = useState<string | null>(null); const [previous, setPrevious] = useState<Notification[]>([]);
  const notifications = useAsync((signal) => api<Page<Notification>>(`/api/v1/notifications?limit=30${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, { signal }), [cursor]);
  const items = cursor ? [...previous, ...(notifications.data?.items ?? [])] : (notifications.data?.items ?? []);
  async function markRead(item: Notification) { if (!item.read_at) await api(`/api/v1/notifications/${item.id}/read`, { method: "POST" }); window.dispatchEvent(new CustomEvent("connecthub:notifications")); if (item.type === "room_invitation") navigate("/app/invitations"); else if (item.room_id) navigate(`/app/rooms/${item.room_id}`); else notifications.reload(); }
  async function markAll() { try { await api("/api/v1/notifications/read-all", { method: "POST" }); toast("All notifications marked read.", "success"); window.dispatchEvent(new CustomEvent("connecthub:notifications")); notifications.reload(); } catch (reason) { toast(errorMessage(reason), "error"); } }
  function more() { if (!notifications.data?.next_cursor) return; setPrevious(items); setCursor(notifications.data.next_cursor); }
  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Stay in the loop</p><h1>Notifications</h1><p>Invitations, mentions, and important room changes.</p></div><Button onClick={markAll} variant="secondary">Mark all read</Button></div><section className="section-card">{notifications.loading && !cursor ? <Skeleton lines={6}/> : notifications.error ? <div className="inline-error">{errorMessage(notifications.error)} <button onClick={notifications.reload}>Retry</button></div> : items.length ? <><div className="notification-list">{items.map((item) => { const content = copy(item); return <button className={`notification-item ${item.read_at ? "" : "unread"}`} key={item.id} onClick={() => markRead(item)}><span className="notification-icon"><Icon name={content.icon}/></span><span><strong>{content.title}</strong><span>{content.text}</span><small>{formatDateTime(item.created_at)}</small></span>{!item.read_at ? <i aria-label="Unread"/> : null}</button>; })}</div>{notifications.data?.next_cursor ? <div className="load-more"><Button busy={notifications.loading} onClick={more} variant="secondary">Load more</Button></div> : null}</> : <EmptyState icon="bell" title="You're all caught up" description="Invitations, mentions, and membership updates will appear here."/>}</section></div>;
}
