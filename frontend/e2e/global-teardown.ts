import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

export default function globalTeardown(): void {
  const python = process.env.CONNECTHUB_PYTHON ?? (process.platform === "win32" ? resolve("../.venv/Scripts/python.exe") : "python");
  const path = process.platform === "win32" ? `C:\\Program Files\\PostgreSQL\\18\\bin;${process.env.PATH ?? ""}` : process.env.PATH;
  execFileSync(python, ["scripts/e2e_database.py", "clean"], {
    cwd: resolve("../backend"),
    env: { ...process.env, PSYCOPG_IMPL: "python", PATH: path },
    stdio: "inherit",
  });
}
