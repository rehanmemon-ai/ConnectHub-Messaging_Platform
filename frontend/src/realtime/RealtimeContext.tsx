/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import type { ConnectionState, ServerEvent, UUID } from "../types/api";
import { useAuth } from "../app/AuthContext";

interface RealtimeValue {
  state: ConnectionState;
  subscribe: (roomId: UUID) => () => void;
  send: (event: Record<string, unknown>) => boolean;
  onEvent: (listener: (event: ServerEvent) => void) => () => void;
}

const RealtimeContext = createContext<RealtimeValue | null>(null);

function isServerEvent(value: unknown): value is ServerEvent {
  return !!value && typeof value === "object" && typeof (value as { type?: unknown }).type === "string";
}

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const { status, invalidate } = useAuth();
  const [state, setState] = useState<ConnectionState>("disconnected");
  const socket = useRef<WebSocket | null>(null);
  const listeners = useRef(new Set<(event: ServerEvent) => void>());
  const subscriptions = useRef(new Set<UUID>());
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<number | undefined>(undefined);
  const heartbeat = useRef<number | undefined>(undefined);
  const active = useRef(false);
  const connectRef = useRef<() => void>(() => undefined);

  const emit = useCallback((event: ServerEvent) => {
    listeners.current.forEach((listener) => listener(event));
    if (event.type === "notification.created") {
      window.dispatchEvent(new CustomEvent("connecthub:notifications"));
    }
  }, []);

  const connect = useCallback(() => {
    if (!active.current || socket.current?.readyState === WebSocket.OPEN) return;
    setState(reconnectAttempt.current ? "reconnecting" : "connecting");
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const next = new WebSocket(`${protocol}//${window.location.host}/ws`);
    socket.current = next;
    next.onopen = () => {
      reconnectAttempt.current = 0;
      setState("connected");
      subscriptions.current.forEach((roomId) =>
        next.send(JSON.stringify({ type: "room.subscribe", room_id: roomId })),
      );
      window.clearInterval(heartbeat.current);
      heartbeat.current = window.setInterval(() => {
        if (next.readyState === WebSocket.OPEN) {
          next.send(JSON.stringify({ type: "ping", nonce: String(Date.now()) }));
        }
      }, 25_000);
      window.dispatchEvent(new CustomEvent("connecthub:reconnected"));
    };
    next.onmessage = (message) => {
      try {
        const event: unknown = JSON.parse(String(message.data));
        if (!isServerEvent(event)) return;
        if (event.type === "error" && event.error.code === "session_expired") {
          active.current = false;
          invalidate();
        }
        emit(event);
      } catch {
        // Unknown or malformed server data is ignored; it never reaches application state.
      }
    };
    next.onclose = () => {
      window.clearInterval(heartbeat.current);
      socket.current = null;
      if (!active.current) {
        setState("disconnected");
        return;
      }
      setState("reconnecting");
      reconnectAttempt.current += 1;
      const base = Math.min(20_000, 700 * 2 ** Math.min(reconnectAttempt.current, 5));
      reconnectTimer.current = window.setTimeout(() => connectRef.current(), base + Math.random() * 350);
    };
  }, [emit, invalidate]);

  useEffect(() => {
    connectRef.current = connect;
    active.current = status === "authenticated";
    if (active.current) connect();
    else {
      window.clearTimeout(reconnectTimer.current);
      window.clearInterval(heartbeat.current);
      socket.current?.close(1000, "signed_out");
      socket.current = null;
      subscriptions.current.clear();
      setState("disconnected");
    }
    return () => {
      active.current = false;
      window.clearTimeout(reconnectTimer.current);
      window.clearInterval(heartbeat.current);
      socket.current?.close(1000, "unmounted");
    };
  }, [connect, status]);

  const value = useMemo<RealtimeValue>(
    () => ({
      state,
      subscribe(roomId) {
        subscriptions.current.add(roomId);
        if (socket.current?.readyState === WebSocket.OPEN) {
          socket.current.send(JSON.stringify({ type: "room.subscribe", room_id: roomId }));
        }
        return () => {
          subscriptions.current.delete(roomId);
          if (socket.current?.readyState === WebSocket.OPEN) {
            socket.current.send(JSON.stringify({ type: "room.unsubscribe", room_id: roomId }));
          }
        };
      },
      send(event) {
        if (socket.current?.readyState !== WebSocket.OPEN) return false;
        socket.current.send(JSON.stringify(event));
        return true;
      },
      onEvent(listener) {
        listeners.current.add(listener);
        return () => listeners.current.delete(listener);
      },
    }),
    [state],
  );
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtime(): RealtimeValue {
  const context = useContext(RealtimeContext);
  if (!context) throw new Error("useRealtime must be used inside RealtimeProvider");
  return context;
}
