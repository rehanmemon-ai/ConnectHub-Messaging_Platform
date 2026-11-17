import { vi } from "vitest";

import type { OwnUser, Room } from "./types/api";

export const currentUser: OwnUser = {
  id: "10000000-0000-4000-8000-000000000001",
  username: "rehan",
  display_name: "Rehan Khan",
  email: "rehan@example.test",
  created_at: "2026-11-16T08:00:00Z",
  updated_at: "2026-11-16T08:00:00Z",
};

export const room: Room = {
  id: "20000000-0000-4000-8000-000000000001",
  name: "Architecture Guild",
  description: "A room for careful engineering decisions.",
  visibility: "private",
  membership: { role: "owner", joined_at: "2026-11-16T08:10:00Z" },
  created_at: "2026-11-16T08:10:00Z",
};

export function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function apiError(status: number, code: string, message: string): Response {
  return json({ error: { code, message, details: [] } }, status);
}

export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  readonly url: string;
  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string | URL) {
    this.url = String(url);
    FakeWebSocket.instances.push(this);
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  serverMessage(value: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(value) }));
  }

  send(value: string) {
    this.sent.push(value);
  }

  close(code = 1000, reason = "") {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close", { code, reason }));
  }
}

export function installWebSocket() {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
}

export function installFetch(
  handler: (url: string, init: RequestInit) => Response | Promise<Response>,
) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) =>
    await handler(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, init),
  );
}
