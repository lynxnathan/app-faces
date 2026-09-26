import { randomBytes } from "node:crypto";
import { writeFile } from "node:fs/promises";
const token = randomBytes(32).toString("base64url");
const reviewers = JSON.stringify([{ name: "Nathan", role: "admin", token }]);
try {
  await writeFile(
    ".dev.vars",
    `RECEIPT_SECRET=${JSON.stringify(randomBytes(32).toString("base64url"))}\nREVIEWERS='${reviewers}'\n`,
    { flag: "wx", mode: 0o600 },
  );
  console.log(
    "Created private .dev.vars with random local-only secrets. Moderator token is inside that file; no secrets printed.",
  );
} catch (e) {
  if (e.code === "EEXIST") console.log(".dev.vars already exists; preserved.");
  else throw e;
}
