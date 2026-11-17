import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const password = "Correct-Horse-Battery-44";

async function registerAndLogin(page: Page, username: string): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Display name").fill(`${username} display`);
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Email").fill(`${username}@example.test`);
  await page.getByLabel(/^Password/).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Account created")).toBeVisible();
  await page.getByLabel("Username or email").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Good .*?/ })).toBeVisible();
}

async function createRoom(page: Page, name: string, visibility: "Public" | "Private"): Promise<string> {
  await page.getByRole("link", { name: "My rooms" }).click();
  await page.getByRole("button", { name: "Create room" }).first().click();
  await page.getByLabel("Room name").fill(name);
  await page.getByLabel(visibility).check();
  await page.getByRole("button", { name: "Create room" }).last().click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  return page.url().split("/").at(-1)!;
}

test("real multi-user public and private room journeys", async ({ browser }) => {
  const ownerContext = await browser.newContext();
  const memberContext = await browser.newContext();
  const outsiderContext = await browser.newContext();
  const owner = await ownerContext.newPage();
  const member = await memberContext.newPage();
  const outsider = await outsiderContext.newPage();

  await registerAndLogin(owner, "e2e_owner");
  const publicRoomId = await createRoom(owner, "E2E public room", "Public");
  await owner.getByLabel("Message E2E public room").fill("owner persisted message");
  await owner.getByRole("button", { name: "Send message" }).click();
  await expect(owner.getByRole("article").getByText("owner persisted message")).toBeVisible();

  await registerAndLogin(member, "e2e_member");
  await member.getByRole("link", { name: "Discover" }).click();
  await member.getByLabel("Search rooms").fill("E2E public room");
  await member.getByRole("button", { name: "Search" }).click();
  await member.getByRole("button", { name: "Join room" }).click();
  await member.getByRole("link", { name: "Open" }).click();
  await expect(member.getByText("owner persisted message")).toBeVisible();
  await member.getByLabel("Message E2E public room").fill("member realtime message");
  await member.getByRole("button", { name: "Send message" }).click();
  await expect(owner.getByText("member realtime message")).toBeVisible();

  const duplicateIds = await member.evaluate(async ({ roomId }) => {
    const csrf = document.cookie.split("; ").find((item) => item.startsWith("connecthub_csrf="))?.split("=")[1];
    const clientId = crypto.randomUUID();
    const send = () => fetch(`/api/v1/rooms/${roomId}/messages`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(csrf ?? "") },
      body: JSON.stringify({ client_id: clientId, content: "idempotent browser message" }),
    }).then((response) => response.json());
    const first = await send(); const second = await send();
    return [first.message.id, second.message.id];
  }, { roomId: publicRoomId });
  expect(duplicateIds[0]).toBe(duplicateIds[1]);

  const privateRoomId = await createRoom(owner, "E2E private room", "Private");
  await owner.getByRole("button", { name: /Room details/ }).click();
  await owner.getByRole("button", { name: "Invite member" }).click();
  await owner.getByLabel("Username").fill("e2e_member");
  await owner.getByRole("button", { name: "Send invitation" }).click();
  await expect(owner.getByText("@e2e_member", { exact: true })).toBeVisible();

  await member.getByRole("link", { name: "Invitations" }).click();
  await expect(member.getByRole("heading", { name: "E2E private room" })).toBeVisible();
  await member.getByRole("button", { name: "Accept" }).click();
  await member.waitForURL(`/app/rooms/${privateRoomId}`);
  await expect(member.getByRole("heading", { name: "E2E private room" })).toBeVisible();
  await member.reload();
  await expect(member.getByRole("heading", { name: "E2E private room" })).toBeVisible();

  await registerAndLogin(outsider, "e2e_outsider");
  const denied = await outsider.evaluate((roomId) => fetch(`/api/v1/rooms/${roomId}`, { credentials: "include" }).then((response) => response.status), privateRoomId);
  expect(denied).toBe(404);

  await owner.getByRole("button", { name: "Invite member" }).click();
  await owner.getByLabel("Username").fill("e2e_outsider");
  await owner.getByRole("button", { name: "Send invitation" }).click();
  await owner.reload();
  await expect(owner.getByText("@e2e_outsider", { exact: true })).toBeVisible();
  await owner.getByLabel("Message E2E private room").fill("summary source message");
  await owner.getByRole("button", { name: "Send message" }).click();
  await owner.getByRole("button", { name: /Summarize conversation/ }).click();
  await expect(owner.getByText(/AI summaries are not configured/)).toBeVisible();

  await ownerContext.close();
  await memberContext.close();
  await outsiderContext.close();
});

test("session restoration, exact search, responsive navigation, and critical accessibility", async ({ page }) => {
  await registerAndLogin(page, "e2e_accessible");
  await createRoom(page, "E2E accessible room", "Public");
  await page.getByLabel("Message E2E accessible room").fill("searchable persistence marker");
  await page.getByRole("button", { name: "Send message" }).click();
  await page.reload();
  await expect(page.getByText("searchable persistence marker")).toBeVisible();
  await page.getByRole("link", { name: "Search" }).click();
  await page.getByLabel("Search query").fill("persistence marker");
  await page.getByRole("button", { name: "Search messages" }).click();
  await expect(page.getByText("searchable persistence marker")).toBeVisible();

  const desktopAudit = await new AxeBuilder({ page }).analyze();
  expect(desktopAudit.violations.filter((item) => ["critical", "serious"].includes(item.impact ?? ""))).toEqual([]);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
  const mobileAudit = await new AxeBuilder({ page }).analyze();
  expect(mobileAudit.violations.filter((item) => ["critical", "serious"].includes(item.impact ?? ""))).toEqual([]);
});

test("bounded authenticated HTTP load smoke remains responsive", async ({ page }) => {
  await registerAndLogin(page, "e2e_load");
  const roomId = await createRoom(page, "E2E load room", "Public");
  const result = await page.evaluate(async (id) => {
    const csrf = decodeURIComponent(document.cookie.split("; ").find((item) => item.startsWith("connecthub_csrf="))?.split("=")[1] ?? "");
    const timings: number[] = [];
    const statuses: number[] = [];
    for (let index = 0; index < 20; index += 1) {
      const started = performance.now();
      const response = await fetch(`/api/v1/rooms/${id}/messages`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ client_id: crypto.randomUUID(), content: `bounded load message ${index}` }),
      });
      timings.push(performance.now() - started);
      statuses.push(response.status);
    }
    timings.sort((left, right) => left - right);
    const ready = await fetch("/health/ready");
    return { statuses, p95: timings[Math.ceil(timings.length * 0.95) - 1], ready: ready.status };
  }, roomId);
  expect(result.statuses.every((status) => status === 201)).toBe(true);
  expect(result.ready).toBe(200);
  expect(result.p95).toBeLessThan(2_000);
});
