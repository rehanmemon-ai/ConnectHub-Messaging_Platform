import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage, RegisterPage } from "./AuthPages";

vi.mock("../../app/AuthContext", () => ({
  useAuth: () => ({ login: vi.fn(), register: vi.fn() }),
}));

describe("password visibility controls", () => {
  beforeEach(() => history.replaceState({}, "", "/login"));

  it("toggles the login password without changing its value or submitting", () => {
    render(<LoginPage />);
    const input = screen.getByLabelText("Password") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "kept-secret-value" } });
    expect(input.type).toBe("password");
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(input.type).toBe("text");
    expect(input.value).toBe("kept-secret-value");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
  });

  it("controls registration password and confirmation independently", () => {
    render(<RegisterPage />);
    const password = screen.getByLabelText("Password") as HTMLInputElement;
    const confirmation = screen.getByLabelText("Confirm password") as HTMLInputElement;
    fireEvent.change(password, { target: { value: "first-password-value" } });
    fireEvent.change(confirmation, { target: { value: "second-password-value" } });
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password.type).toBe("text");
    expect(confirmation.type).toBe("password");
    expect(password.value).toBe("first-password-value");
    expect(confirmation.value).toBe("second-password-value");
  });
});
