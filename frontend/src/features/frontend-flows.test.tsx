import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { isNearBottom, preservedScrollTop } from "./chat/scroll";
import type { Message, Notification } from "../types/api";
import { apiError, currentUser, FakeWebSocket, installFetch, installWebSocket, json, room } from "../test-utils";

const otherUser = {
  id: "10000000-0000-4000-8000-000000000002",
  username: "anika",
  display_name: "Anika Rao",
  created_at: "2026-11-16T08:00:00Z",
};

const unsafeMessage: Message = {
  id: "30000000-0000-4000-8000-000000000001",
  room_id: room.id,
  sender: otherUser,
  content: '<img src=x onerror="window.__unsafe=1"> hello',
  created_at: "2026-11-16T09:00:00Z",
};

function roomFetch(options: { aiUnavailable?: boolean; failFirstSend?: boolean } = {}) {
  let sendCount = 0;
  return installFetch((url, init) => {
    const method = (init.method ?? "GET").toUpperCase();
    if (url.endsWith("/users/me")) return json({ user: currentUser });
    if (url.includes("unread-count")) return json({ count: 2 });
    if (url.endsWith(`/rooms/${room.id}/messages`) && method === "POST") {
      sendCount += 1;
      if (options.failFirstSend && sendCount === 1) return apiError(503, "service_unavailable", "Unavailable.");
      const body = JSON.parse(String(init.body));
      return json({ message: { ...unsafeMessage, id: "30000000-0000-4000-8000-000000000099", sender: currentUser, content: body.content, created_at: "2026-11-16T09:05:00Z" } }, 201);
    }
    if (url.endsWith(`/rooms/${room.id}/summaries`) && method === "POST") {
      return options.aiUnavailable
        ? apiError(503, "ai_not_configured", "AI features are not configured.")
        : json({});
    }
    if (url.includes(`/rooms/${room.id}/messages?`)) return json({ items: [unsafeMessage], next_cursor: null });
    if (url.endsWith(`/rooms/${room.id}/members?limit=100`)) return json({ items: [
      { user_id: currentUser.id, username: currentUser.username, display_name: currentUser.display_name, role: "owner", joined_at: room.created_at, online: true, last_seen_at: null },
      { user_id: otherUser.id, username: otherUser.username, display_name: otherUser.display_name, role: "member", joined_at: room.created_at, online: false, last_seen_at: room.created_at },
    ], next_cursor: null });
    if (url.endsWith(`/rooms/${room.id}/read-receipts`)) return json([]);
    if (url.endsWith(`/rooms/${room.id}/embeddings/status`)) return json({ total_messages: 1, indexed_messages: 0, pending_jobs: 0, failed_jobs: 0, provider: "disabled", model: "disabled", storage: "postgresql" });
    if (url.endsWith(`/rooms/${room.id}`)) return json({ room });
    if (url.endsWith(`/rooms/${room.id}/read-position`)) return json({});
    return json({});
  });
}

describe("room and realtime flows", () => {
  beforeEach(() => {
    history.replaceState({}, "", `/app/rooms/${room.id}`);
    installWebSocket();
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders persisted message content as inert text", async () => {
    roomFetch();
    render(<App />);
    expect(await screen.findByRole("heading", { name: room.name })).toBeInTheDocument();
    expect(screen.getByText(unsafeMessage.content)).toBeInTheDocument();
    expect(document.querySelector(".message-body img")).toBeNull();
  });

  it("subscribes once connected and applies only in-room realtime messages", async () => {
    roomFetch();
    render(<App />);
    await screen.findByRole("heading", { name: room.name });
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const socket = FakeWebSocket.instances[0];
    socket.open();
    await waitFor(() => expect(socket.sent.map((value) => JSON.parse(value))).toContainEqual({ type: "room.subscribe", room_id: room.id }));
    socket.serverMessage({ type: "message.created", message: { ...unsafeMessage, id: "30000000-0000-4000-8000-000000000002", content: "Delivered live" } });
    expect(await screen.findByText("Delivered live")).toBeInTheDocument();
    socket.serverMessage({ type: "message.created", message: { ...unsafeMessage, id: "30000000-0000-4000-8000-000000000003", room_id: "20000000-0000-4000-8000-000000000999", content: "Wrong room" } });
    expect(screen.queryByText("Wrong room")).not.toBeInTheDocument();
  });

  it("offers a jump control instead of stealing scroll position for new messages", async () => {
    roomFetch();
    render(<App />);
    await screen.findByRole("heading", { name: room.name });
    const scroller = document.querySelector(".message-scroll") as HTMLDivElement;
    Object.defineProperties(scroller, {
      scrollHeight: { configurable: true, value: 1_000 },
      clientHeight: { configurable: true, value: 400 },
    });
    await new Promise((resolve) => window.setTimeout(resolve, 25));
    scroller.scrollTop = 100;
    fireEvent.scroll(scroller);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Jump to latest" })).not.toBeInTheDocument());
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.serverMessage({ type: "message.created", message: { ...unsafeMessage, id: "30000000-0000-4000-8000-000000000004", content: "New while reading history" } });
    const jump = await screen.findByRole("button", { name: "Jump to latest" });
    const scrollTo = vi.spyOn(scroller, "scrollTo");
    fireEvent.click(jump);
    expect(scrollTo).toHaveBeenCalledWith({ top: 1_000, behavior: "smooth" });
    expect(screen.queryByRole("button", { name: "Jump to latest" })).not.toBeInTheDocument();
  });

  it("calculates near-bottom following and preserves position when prepending history", () => {
    expect(isNearBottom({ scrollHeight: 1_000, scrollTop: 520, clientHeight: 400 })).toBe(true);
    expect(isNearBottom({ scrollHeight: 1_000, scrollTop: 100, clientHeight: 400 })).toBe(false);
    expect(preservedScrollTop(75, 900, 1_250)).toBe(425);
  });

  it("keeps the idempotency key when a failed message is retried", async () => {
    const fetch = roomFetch({ failFirstSend: true });
    render(<App />);
    const composer = await screen.findByLabelText(`Message ${room.name}`);
    fireEvent.change(composer, { target: { value: "Retry this safely" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    const retry = await screen.findByRole("button", { name: /retry same message/i });
    fireEvent.click(retry);
    expect(await screen.findByText("Retry this safely")).toBeInTheDocument();
    const bodies = fetch.mock.calls
      .filter(([input, init]) => String(input).endsWith(`/rooms/${room.id}/messages`) && init?.method === "POST")
      .map(([, init]) => JSON.parse(String(init?.body)));
    expect(bodies).toHaveLength(2);
    expect(bodies[0].client_id).toBe(bodies[1].client_id);
  });

  it("emits typing start and stop around composer activity", async () => {
    roomFetch();
    render(<App />);
    const composer = await screen.findByLabelText(`Message ${room.name}`);
    const socket = FakeWebSocket.instances[0];
    socket.open();
    fireEvent.change(composer, { target: { value: "Hello" } });
    fireEvent.blur(composer);
    await waitFor(() => expect(socket.sent.map((value) => JSON.parse(value))).toEqual(expect.arrayContaining([
      { type: "typing.start", room_id: room.id },
      { type: "typing.stop", room_id: room.id },
    ])));
  });

  it("keeps messaging usable when AI summaries are unavailable", async () => {
    roomFetch({ aiUnavailable: true });
    render(<App />);
    const composer = await screen.findByLabelText(`Message ${room.name}`);
    fireEvent.click(screen.getByRole("button", { name: /summarize conversation/i }));
    expect(await screen.findByText(/AI summaries are not configured/i)).toBeInTheDocument();
    expect(composer).toBeEnabled();
  });
});

describe("discovery and notifications", () => {
  beforeEach(() => installWebSocket());
  afterEach(() => vi.restoreAllMocks());

  it("discovers and joins a public room", async () => {
    history.replaceState({}, "", "/app/discover");
    const publicRoom = { ...room, visibility: "public" as const, membership: null };
    const fetch = installFetch((url, init) => {
      if (url.endsWith("/users/me")) return json({ user: currentUser });
      if (url.includes("unread-count")) return json({ count: 0 });
      if (url.includes("/api/v1/rooms?") && (init.method ?? "GET") === "GET") return json({ items: [publicRoom], next_cursor: null });
      if (url.endsWith(`/rooms/${room.id}/membership`)) return json({});
      return json({});
    });
    render(<App />);
    expect(await screen.findByText(room.name)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /join room/i }));
    await waitFor(() => expect(fetch.mock.calls.some(([input, init]) => String(input).endsWith(`/rooms/${room.id}/membership`) && init?.method === "POST")).toBe(true));
    expect(await screen.findByText(`Joined ${room.name}.`)).toBeInTheDocument();
  });

  it("marks all notifications read through the mutation endpoint", async () => {
    history.replaceState({}, "", "/app/notifications");
    const notification: Notification = { id: "40000000-0000-4000-8000-000000000001", type: "message_mention", room_id: room.id, actor_id: otherUser.id, message_id: unsafeMessage.id, invitation_id: null, metadata: {}, created_at: unsafeMessage.created_at, read_at: null };
    const fetch = installFetch((url) => {
      if (url.endsWith("/users/me")) return json({ user: currentUser });
      if (url.includes("unread-count")) return json({ count: 1 });
      if (url.includes("/notifications?")) return json({ items: [notification], next_cursor: null });
      if (url.endsWith("/notifications/read-all")) return json({ updated: 1 });
      return json({});
    });
    render(<App />);
    expect(await screen.findByText("You were mentioned")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /mark all read/i }));
    expect(await screen.findByText(/all notifications marked read/i)).toBeInTheDocument();
    expect(fetch.mock.calls.some(([input, init]) => String(input).endsWith("/notifications/read-all") && init?.method === "POST")).toBe(true);
  });

  it("runs genuine semantic search against the room-scoped endpoint", async () => {
    history.replaceState({}, "", "/app/search");
    const semanticMessage = { ...unsafeMessage, content: "We chose cursor pagination." };
    const fetch = installFetch((url, init) => {
      if (url.endsWith("/users/me")) return json({ user: currentUser });
      if (url.includes("unread-count")) return json({ count: 0 });
      if (url.includes("/users/me/rooms")) return json({ items: [{ room, role: "owner", joined_at: room.created_at }], next_cursor: null });
      if (url.endsWith(`/rooms/${room.id}/embeddings/status`)) return json({ total_messages: 4, indexed_messages: 4, pending_jobs: 0, failed_jobs: 0, provider: "gemini", model: "embedding-001", storage: "postgresql_jsonb_exact_cosine" });
      if (url.endsWith(`/rooms/${room.id}/messages/semantic-search`) && init.method === "POST") return json({ items: [{ message: semanticMessage, similarity: 0.92 }], indexed_candidates: 4, unindexed_messages: 0 });
      return json({});
    });
    render(<App />);
    await screen.findByRole("heading", { name: /search conversations/i });
    fireEvent.click(screen.getByRole("button", { name: /semantic/i }));
    fireEvent.change(screen.getByLabelText(/search query/i), { target: { value: "How did pagination work?" } });
    fireEvent.click(screen.getByRole("button", { name: /search messages/i }));
    expect(await screen.findByText("We chose cursor pagination.")).toBeInTheDocument();
    expect(screen.getByText("92% match")).toBeInTheDocument();
    expect(fetch.mock.calls.some(([input]) => String(input).endsWith(`/rooms/${room.id}/messages/semantic-search`))).toBe(true);
  });
});
