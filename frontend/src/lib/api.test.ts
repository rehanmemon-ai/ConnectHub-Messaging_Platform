import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, errorMessage } from "./api";
import { apiError, installFetch, json } from "../test-utils";

describe("API client", () => {
  afterEach(() => {
    document.cookie = "connecthub_csrf=; Max-Age=0; path=/";
    vi.restoreAllMocks();
  });

  it("sends credentials and the decoded CSRF cookie for mutations", async () => {
    document.cookie = "connecthub_csrf=token%2Fwith%2Bsymbols; path=/";
    const fetch = installFetch(() => json({ ok: true }));
    await api("/api/v1/example", { method: "POST", body: { value: 1 } });
    const init = fetch.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("token/with+symbols");
  });

  it("does not add CSRF to safe reads", async () => {
    document.cookie = "connecthub_csrf=secret; path=/";
    const fetch = installFetch(() => json({ ok: true }));
    await api("/api/v1/example");
    expect(new Headers(fetch.mock.calls[0][1]?.headers).has("X-CSRF-Token")).toBe(false);
  });

  it("preserves the structured backend error contract", async () => {
    installFetch(() => apiError(409, "username_taken", "That username is unavailable."));
    await expect(api("/api/v1/example")).rejects.toMatchObject({
      status: 409,
      code: "username_taken",
      message: "That username is unavailable.",
    });
  });

  it("maps service failures to a safe user-facing message", () => {
    expect(errorMessage(new ApiError(503))).toMatch(/temporarily unavailable/i);
  });
});
