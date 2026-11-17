import { useEffect } from "react";

import { AuthProvider, useAuth } from "./app/AuthContext";
import { AppShell } from "./app/AppShell";
import { navigate, usePath } from "./app/router";
import { ToastProvider } from "./app/ToastContext";
import { Icon } from "./components/ui/Icon";
import { LoginPage, RegisterPage } from "./features/auth/AuthPages";
import { ChatPage } from "./features/chat/ChatPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { NotificationsPage } from "./features/notifications/NotificationsPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { DiscoverPage, MyRoomsPage } from "./features/rooms/RoomsPage";
import { InvitationsPage } from "./features/rooms/InvitationsPage";
import { SearchPage } from "./features/search/SearchPage";
import { RealtimeProvider } from "./realtime/RealtimeContext";

function LoadingScreen() {
  return <main className="loading-screen" aria-live="polite"><span className="brand-mark"><Icon name="chat"/></span><div className="loading-bar"><span/></div><p>Restoring your workspace…</p></main>;
}

function Routes() {
  const path = usePath(); const { status } = useAuth();
  const isPublic = path === "/login" || path === "/register";
  useEffect(() => {
    if (status === "anonymous" && !isPublic) navigate("/login", { replace: true });
    if (status === "authenticated" && isPublic) navigate("/app", { replace: true });
    if (path === "/") navigate(status === "authenticated" ? "/app" : "/login", { replace: true });
  }, [isPublic, path, status]);
  if (status === "loading" || path === "/") return <LoadingScreen/>;
  if (isPublic) return path === "/register" ? <RegisterPage/> : <LoginPage/>;
  if (status !== "authenticated") return <LoadingScreen/>;
  let page: React.ReactNode;
  const roomMatch = path.match(/^\/app\/rooms\/([0-9a-f-]+)$/i);
  if (roomMatch) page = <ChatPage roomId={roomMatch[1]}/>;
  else if (path === "/app") page = <DashboardPage/>;
  else if (path === "/app/discover") page = <DiscoverPage/>;
  else if (path === "/app/rooms") page = <MyRoomsPage/>;
  else if (path === "/app/invitations") page = <InvitationsPage/>;
  else if (path === "/app/notifications") page = <NotificationsPage/>;
  else if (path === "/app/search") page = <SearchPage/>;
  else if (path === "/app/profile") page = <ProfilePage/>;
  else page = <div className="empty-state"><h1>Page not found</h1><p>That ConnectHub page does not exist.</p><button className="button button-primary" onClick={() => navigate("/app")}>Return home</button></div>;
  return <AppShell>{page}</AppShell>;
}

export default function App() {
  return <AuthProvider><RealtimeProvider><ToastProvider><Routes/></ToastProvider></RealtimeProvider></AuthProvider>;
}
