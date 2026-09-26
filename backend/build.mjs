import { build } from "esbuild";
import { mkdir, writeFile } from "node:fs/promises";
const result = await build({
  entryPoints: ["src/admin.ts"],
  bundle: true,
  format: "iife",
  write: false,
  target: "es2023",
  minify: true,
});
await mkdir("build", { recursive: true });
await writeFile("build/admin.bundle.txt", result.outputFiles[0].text);
