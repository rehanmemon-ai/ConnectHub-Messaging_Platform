import { useEffect, useState } from "react";

import { api } from "../lib/api";
import { Avatar, Badge } from "../components/ui/primitives";
import { Icon } from "../components/ui/Icon";
import { useAuth } from "./AuthContext";
import { Link, navigate, usePath } from "./router";
import { useRealtime } from "../realtime/RealtimeContext";

const nav = [
  ["/app", "home", "Overview"], ["/app/discover", "compass", "Discover"],
  ["/app/rooms", "chat", "My rooms"], ["/app/invitations", "mail", "Invitations"],
  ["/app/notifications", "bell", "Notifications"], ["/app/search", "search", "Search"],
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { state } = useRealtime();
  const path = usePath();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [dark, setDark] = useState(() => localStorage.getItem("connecthub-theme") !== "light");

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("connecthub-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    const refresh = () => api<{ count: number }>("/api/v1/notifications/unread-count").then((r) => setUnread(r.count)).catch(() => undefined);
    refresh();
    window.addEventListener("connecthub:notifications", refresh);
    window.addEventListener("connecthub:reconnected", refresh);
    return () => { window.removeEventListener("connecthub:notifications", refresh); window.removeEventListener("connecthub:reconnected", refresh); };
  }, []);

  async function signOut() {
    await logout();
    navigate("/login", { replace: true });
  }
  return <div className="app-layout">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
      <div className="brand"><span className="brand-mark"><Icon name="chat"/></span><span><strong>ConnectHub</strong><small>Conversations that matter</small></span><button aria-label="Close navigation" className="icon-button mobile-only" onClick={() => setOpen(false)}><Icon name="x"/></button></div>
      <nav aria-label="Primary navigation" className="primary-nav">{nav.map(([to, icon, label]) => <Link className={path === to || (to !== "/app" && path.startsWith(to)) ? "nav-link active" : "nav-link"} key={to} onClick={() => setOpen(false)} to={to}><Icon name={icon}/><span>{label}</span>{label === "Notifications" && unread > 0 ? <Badge tone="accent">{unread > 99 ? "99+" : unread}</Badge> : null}</Link>)}</nav>
      <div className="sidebar-footer"><div className="connection-pill"><span className={`status-dot status-${state}`}/><span>{state === "connected" ? "Live updates on" : state}</span></div><Link className="profile-chip" to="/app/profile"><Avatar name={user?.display_name ?? "User"}/><span><strong>{user?.display_name}</strong><small>@{user?.username}</small></span><Icon name="chevron" size={16}/></Link><button className="nav-link" onClick={signOut}><Icon name="logout"/><span>Sign out</span></button></div>
    </aside>
    {open ? <button aria-label="Close navigation overlay" className="sidebar-overlay" onClick={() => setOpen(false)}/> : null}
    <div className="app-main"><header className="topbar"><button aria-label="Open navigation" className="icon-button mobile-only" onClick={() => setOpen(true)}><Icon name="menu"/></button><div className="topbar-spacer"/><button aria-label={dark ? "Use light theme" : "Use dark theme"} className="icon-button" onClick={() => setDark((value) => !value)}><Icon name={dark ? "sun" : "moon"}/></button><Link aria-label="Notifications" className="notification-button" to="/app/notifications"><Icon name="bell"/>{unread > 0 ? <span className="notification-count">{unread}</span> : null}</Link></header><main id="main-content" className="page-container">{children}</main></div>
  </div>;
}
