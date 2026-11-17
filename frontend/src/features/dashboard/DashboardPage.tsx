import { api, errorMessage } from "../../lib/api";
import { useAsync } from "../../lib/useAsync";
import type { Invitation, JoinedRoom, Page } from "../../types/api";
import { useAuth } from "../../app/AuthContext";
import { Link } from "../../app/router";
import { Badge, EmptyState, Skeleton } from "../../components/ui/primitives";
import { Icon } from "../../components/ui/Icon";

export function DashboardPage() {
  const { user } = useAuth();
  const rooms = useAsync((signal) => api<Page<JoinedRoom>>("/api/v1/users/me/rooms?limit=6", { signal }), []);
  const invitations = useAsync((signal) => api<Page<Invitation>>("/api/v1/users/me/invitations?limit=3", { signal }), []);
  const hour = new Date().getHours(); const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  return <div className="page-stack"><section className="welcome-banner"><div><p className="eyebrow">Your conversation home</p><h1>{greeting}, {user?.display_name.split(" ")[0]}.</h1><p>Pick up where you left off or discover a room worth joining.</p></div><Link className="button button-primary" to="/app/discover"><Icon name="compass"/> Explore rooms</Link></section><div className="metric-grid"><Link className="metric-card" to="/app/rooms"><span className="metric-icon"><Icon name="chat"/></span><span><strong>{rooms.data?.items.length ?? "—"}</strong><small>Recent rooms</small></span></Link><Link className="metric-card" to="/app/invitations"><span className="metric-icon amber"><Icon name="mail"/></span><span><strong>{invitations.data?.items.length ?? "—"}</strong><small>Pending invites</small></span></Link><Link className="metric-card" to="/app/search"><span className="metric-icon violet"><Icon name="search"/></span><span><strong>2 ways</strong><small>to search messages</small></span></Link></div><section className="section-card"><div className="section-heading"><div><p className="eyebrow">Jump back in</p><h2>Your rooms</h2></div><Link to="/app/rooms">View all <Icon name="chevron" size={16}/></Link></div>{rooms.loading ? <Skeleton lines={4}/> : rooms.error ? <div className="inline-error">{errorMessage(rooms.error)} <button onClick={rooms.reload}>Try again</button></div> : rooms.data?.items.length ? <div className="room-grid">{rooms.data.items.map(({ room, role }) => <Link className="room-card" key={room.id} to={`/app/rooms/${room.id}`}><div className="room-card-top"><span className="room-icon"><Icon name={room.visibility === "private" ? "lock" : "globe"}/></span><Badge tone={role === "owner" ? "accent" : "neutral"}>{role}</Badge></div><h3>{room.name}</h3><p>{room.description || "A room ready for conversation."}</p><span className="room-link">Open conversation <Icon name="chevron" size={15}/></span></Link>)}</div> : <EmptyState action={<Link className="button button-primary" to="/app/discover">Find a room</Link>} description="Join a public room or create your own space." title="Your room list is waiting"/>}</section></div>;
}
