import { Miniflare } from "miniflare";
import { build } from "esbuild";
import { readFile, readdir } from "node:fs/promises";
const built = await build({
  entryPoints: ["src/index.ts"],
  bundle: true,
  format: "esm",
  write: false,
  target: "es2023",
  loader: { ".txt": "text" },
});
const mf = new Miniflare({
  host: "127.0.0.1",
  port: 8791,
  workers: [
    {
      name: "app",
      modules: true,
      script: built.outputFiles[0].text,
      compatibilityDate: "2026-07-30",
      d1Databases: ["DB"],
      ratelimits: {
        UPLOAD_LIMIT: {
          namespace_id: "1001",
          simple: { limit: 100, period: 60 },
        },
      },
      bindings: {
        RECEIPT_SECRET: "isolated-e2e-secret-not-for-production",
        REVIEWERS: JSON.stringify([
          { name: "Nathan", token: "e2e-admin", role: "admin" },
          { name: "Reviewer", token: "e2e-reviewer", role: "reviewer" },
        ]),
      },
    },
  ],
});
const db = await mf.getD1Database("DB");
for (const file of (await readdir("migrations"))
  .filter((f) => f.endsWith(".sql"))
  .sort())
  for (const sql of (await readFile("migrations/" + file, "utf8"))
    .split(";")
    .filter((s) => s.trim()))
    await db.prepare(sql).run();
console.log("UI E2E ready at " + (await mf.ready));
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => void mf.dispose().then(() => process.exit(0)));
