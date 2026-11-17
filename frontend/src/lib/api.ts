import type { ApiErrorShape } from "../types/api";

export class ApiError extends Error {
  status: number;
  code: string;
  details: ApiErrorShape["error"]["details"];
  requestId?: string;

  constructor(status: number, payload?: ApiErrorShape) {
    super(payload?.error.message ?? "ConnectHub could not complete that request.");
    this.name = "ApiError";
    this.status = status;
    this.code = payload?.error.code ?? "request_failed";
    this.details = payload?.error.details ?? [];
    this.requestId = payload?.error.request_id;
  }
}

function cookie(name: string): string | undefined {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length);
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  csrf?: boolean;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }
  const method = (options.method ?? "GET").toUpperCase();
  if (options.csrf !== false && !["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = cookie("connecthub_csrf");
    if (token) headers.set("X-CSRF-Token", decodeURIComponent(token));
  }
  const response = await fetch(path, {
    ...options,
    method,
    headers,
    body,
    credentials: "include",
  });
  if (!response.ok) {
    let payload: ApiErrorShape | undefined;
    try {
      payload = (await response.json()) as ApiErrorShape;
    } catch {
      payload = undefined;
    }
    throw new ApiError(response.status, payload);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "Too many attempts. Please pause and try again.";
    if (error.status >= 500) return "The service is temporarily unavailable. Please try again.";
    return error.message;
  }
  if (error instanceof DOMException && error.name === "AbortError") return "";
  return "We could not reach ConnectHub. Check your connection and try again.";
}

export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  return Object.fromEntries(
    error.details.flatMap((detail) =>
      detail.field && detail.message ? [[detail.field, detail.message]] : [],
    ),
  );
}
