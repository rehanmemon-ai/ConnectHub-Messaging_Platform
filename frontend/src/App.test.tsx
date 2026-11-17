import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { apiError, currentUser, installFetch, installWebSocket, json } from "./test-utils";

describe("authentication experience", () => {
  beforeEach(() => {
    history.replaceState({}, "", "/login");
    installWebSocket();
  });

  afterEach(() => vi.restoreAllMocks());

  it("restores an authenticated session without flashing the login page", async () => {
    history.replaceState({}, "", "/app");
    let resolveSession!: (response: Response) => void;
    installFetch((url) => {
      if (url.endsWith("/users/me")) return new Promise((resolve) => { resolveSession = resolve; });
      if (url.includes("unread-count")) return json({ count: 0 });
      if (url.includes("/rooms")) return json({ items: [], next_cursor: null });
      if (url.includes("/invitations")) return json({ items: [], next_cursor: null });
      return json({});
    });
    render(<App />);
    expect(screen.getByText(/restoring your workspace/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /welcome back/i })).not.toBeInTheDocument();
    resolveSession(json({ user: currentUser }));
    expect(await screen.findByRole("heading", { name: /good .*rehan/i })).toBeInTheDocument();
  });

  it("signs in with the backend session contract", async () => {
    const fetch = installFetch((url) => {
      if (url.endsWith("/users/me")) return apiError(401, "authentication_required", "Authentication required.");
      if (url.endsWith("/auth/login")) return json({ user: currentUser });
      if (url.includes("unread-count")) return json({ count: 0 });
      if (url.includes("/rooms") || url.includes("/invitations")) return json({ items: [], next_cursor: null });
      return json({});
    });
    render(<App />);
    await screen.findByRole("heading", { name: /welcome back/i });
    fireEvent.change(screen.getByLabelText(/username or email/i), { target: { value: "rehan" } });
    fireEvent.change(screen.getAllByLabelText(/password/i)[0], { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("heading", { name: /good .*rehan/i })).toBeInTheDocument();
    const request = fetch.mock.calls.find(([input]) => String(input).endsWith("/auth/login"));
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ identifier: "rehan", password: "correct horse battery staple" });
  });

  it("shows the backend's safe invalid-credentials message", async () => {
    installFetch((url) => url.endsWith("/users/me")
      ? apiError(401, "authentication_required", "Authentication required.")
      : apiError(401, "invalid_credentials", "Invalid username, email, or password."));
    render(<App />);
    await screen.findByRole("heading", { name: /welcome back/i });
    fireEvent.change(screen.getByLabelText(/username or email/i), { target: { value: "unknown" } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid username, email, or password.");
  });

  it("validates registration locally before making a request", async () => {
    history.replaceState({}, "", "/register");
    const fetch = installFetch(() => apiError(401, "authentication_required", "Authentication required."));
    render(<App />);
    await screen.findByRole("heading", { name: /create your account/i });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/use 1–50 characters/i)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("registers, then asks the user to sign in instead of inventing a session", async () => {
    history.replaceState({}, "", "/register");
    const fetch = installFetch((url) => url.endsWith("/users/me")
      ? apiError(401, "authentication_required", "Authentication required.")
      : json({ user: currentUser }, 201));
    render(<App />);
    await screen.findByRole("heading", { name: /create your account/i });
    fireEvent.change(screen.getByLabelText(/display name/i), { target: { value: "Rehan Khan" } });
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "rehan" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "rehan@example.test" } });
    fireEvent.change(screen.getAllByLabelText(/password/i)[0], { target: { value: "correct horse battery staple" } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/account created\. sign in/i)).toBeInTheDocument();
    expect(history.state).toBeTruthy();
    expect(fetch.mock.calls.some(([input]) => String(input).endsWith("/auth/login"))).toBe(false);
  });
});
