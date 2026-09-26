const IMAGE_DOWNLOAD_CONCURRENCY = 4;
const QUEUE_RESULT_LIMIT = 100;
const LOADING_PLACEHOLDER_COUNT = 3;
import { t, locale, initializeLanguage } from "./i18n";
initializeLanguage();
interface Proposal {
  id: string;
  name: string;
  application_id: string;
  variant: string;
  license: string;
  source_url: string;
  duplicates: number;
  status: string;
  reason: string;
  version: number;
  existing_digest: string | null;
  existing_variant: string | null;
  created_at: string;
}
interface Queue {
  reviewer: { name: string; role: string };
  submissions: Proposal[];
}
interface Revision {
  id: number;
  created_at: string;
}
interface Review {
  application_name: string | null;
  application_id: string | null;
  id: number;
  operation: string;
  submission_id: string;
  reviewer: string;
  decision: string;
  reason: string;
  created_at: string;
}
let token = "",
  role = "",
  view = "inbox",
  generation = 0;
let proposals: Proposal[] = [];
let urls: string[] = [];
const images = new Map<string, string>();
const labels = (): Record<string, string> => ({
  approve: t("Approve icon"),
  reject: t("Reject contribution"),
  merge: t("Merge into application"),
  correction: t("Request correction"),
  revoke: t("Revoke icon"),
  approved: t("Approved"),
  pending: t("Pending"),
  rejected: t("Rejected"),
  merged: t("Merged"),
  revoked: t("Revoked"),
  withdrawn: t("Withdrawn"),
  withdraw: t("Withdraw contribution"),
  resubmit: t("Correction submitted"),
  rollback: t("Restore catalog"),
});
function element<T extends HTMLElement>(id: string): T {
  const n = document.getElementById(id);
  if (!n) throw Error(t("Missing element: ") + id);
  return n as T;
}
function node<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  text = "",
  className = "",
): HTMLElementTagNameMap[K] {
  const n = document.createElement(tag);
  n.textContent = text;
  n.className = className;
  return n;
}
function say(text: string, error = false): void {
  const n = element("message");
  n.textContent = text;
  n.classList.toggle("error", error);
}
const message = (e: unknown): string =>
  e instanceof Error ? e.message : t("Operation failed. Try again.");
function date(value: string): string {
  const d = new Date(
    value.includes("T") ? value : value.replace(" ", "T") + "Z",
  );
  return Number.isNaN(d.valueOf())
    ? value
    : d.toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" });
}
let suspendedReview = false,
  suspendedDecision = false;
function requireLogin(): void {
  if (element("workspace").hidden) return;
  const reviewDialog = element<HTMLDialogElement>("review");
  const decisionDialog = element<HTMLDialogElement>("decision");
  suspendedReview = reviewDialog.open;
  suspendedDecision = decisionDialog.open;
  decisionDialog.close();
  reviewDialog.close();
  token = "";
  generation++;
  element("workspace").hidden = true;
  element("login-screen").hidden = false;
  element("login-error").textContent = suspendedDecision
    ? t("Access expired. Sign in to resume. Your draft is saved in this tab.")
    : t("Access expired. Sign in again.");
  const password = element<HTMLInputElement>("token");
  password.value = "";
  password.type = "password";
  element("reveal").setAttribute("aria-label", t("Show password"));
  element("reveal").setAttribute("aria-pressed", "false");
  password.focus();
}
async function api(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  headers.set("Authorization", "Bearer " + token);
  let r: Response;
  try {
    r = await fetch(path, { ...options, headers });
  } catch {
    throw Error(t("Connection failed. Check your connection and retry."));
  }
  if (!r.ok) {
    if (r.status === 401) {
      if (headers.get("Authorization") === "Bearer " + token) requireLogin();
      throw Error(t("Invalid password or expired access. Sign in again."));
    }
    if (r.status === 409)
      throw Error(
        t("Contribution changed. Refresh the queue before reviewing."),
      );
    let detail = "";
    try {
      detail = ((await r.json()) as { error?: string }).error ?? "";
    } catch {}
    if (detail === "Invalid moderator token") {
      if (headers.get("Authorization") === "Bearer " + token) requireLogin();
      throw Error(t("Invalid password or expired access. Sign in again."));
    }
    const translations: Record<string, string> = {
      "Source must be HTTPS without credentials": t(
        "Use an HTTPS source without credentials in the URL.",
      ),
      "Invalid sourceUrl": t("Check the icon source URL."),
      "Invalid reason": t("Enter a reason for this decision."),
      "Invalid license": t("Enter the license or redistribution permission."),
      "Merge target must exist": t(
        "Target application must exist in the catalog.",
      ),
      "Admin required for rollback": t(
        "Only administrators can restore the catalog.",
      ),
      "Admin required for revocation": t(
        "Only administrators can revoke icons.",
      ),
    };
    throw Error(
      r.status === 429
        ? t("Too many attempts. Wait and retry.")
        : translations[detail] ||
            (r.status >= 500
              ? t("Service temporarily unavailable. Try again.")
              : t("Could not save. Check the fields and retry.")),
    );
  }
  return r;
}
function clearImages(): void {
  for (const u of urls) URL.revokeObjectURL(u);
  urls = [];
  images.clear();
}
function empty(title: string, description: string): HTMLElement {
  const box = node("div", "", "empty");
  box.append(node("h2", title), node("p", description));
  return box;
}
function renderQueue(): void {
  const root = element("queue");
  root.replaceChildren();
  const query = element<HTMLInputElement>("search")
    .value.trim()
    .toLocaleLowerCase();
  const shown = proposals.filter((s) =>
    (s.name + " " + s.application_id).toLocaleLowerCase().includes(query),
  );
  element("count").textContent =
    t("Contributions: {count}", { count: shown.length }) +
    (proposals.length === QUEUE_RESULT_LIMIT ? t(" · queue limit: 100") : "");
  if (!shown.length) {
    root.append(
      empty(
        query ? t("No results.") : t("Queue empty."),
        query
          ? t("Try another application name or ID.")
          : t(
              "No contributions with this status. New contributions appear under Pending.",
            ),
      ),
    );
    return;
  }
  const head = node("div", "", "list-head");
  head.append(
    node("span", t("Application")),
    node("span", t("Variant")),
    node("span", t("Received")),
  );
  root.append(head);
  for (const s of shown) {
    const row = node("button", "", "proposal");
    row.type = "button";
    row.setAttribute("aria-label", t("Review {name}", { name: s.name }));
    const app = node("span", "", "app-cell"),
      well = node("span", s.name.slice(0, 1).toUpperCase(), "icon-well");
    well.dataset.iconId = s.id;
    const src = images.get(s.id);
    if (src) {
      const img = node("img");
      img.src = src;
      img.alt = "";
      well.replaceChildren(img);
    }
    const identity = node("span");
    identity.append(
      node("strong", s.name),
      node("span", s.application_id, "app-id"),
    );
    app.append(well, identity);
    row.append(
      app,
      node("span", s.variant === "default" ? t("Default") : s.variant, "badge"),
      node("span", date(s.created_at), "date"),
    );
    row.onclick = () => review(s);
    root.append(row);
  }
}
async function hydrate(snapshot: number): Promise<void> {
  let next = 0;
  await Promise.all(
    Array.from({ length: IMAGE_DOWNLOAD_CONCURRENCY }, async () => {
      while (next < proposals.length && snapshot === generation) {
        const s = proposals[next++];
        if (!s) continue;
        try {
          const blob = await (
            await api(
              "/admin/submissions/" + encodeURIComponent(s.id) + "/icon",
            )
          ).blob();
          if (snapshot !== generation) return;
          const url = URL.createObjectURL(blob);
          urls.push(url);
          images.set(s.id, url);
          const wells = document.querySelectorAll<HTMLElement>(
            `[data-icon-id="${CSS.escape(s.id)}"]`,
          );
          for (const well of wells) {
            const img = node("img");
            img.src = url;
            img.alt = well.dataset.previewLabel ?? "";
            well.replaceChildren(img);
          }
        } catch {}
      }
    }),
  );
}
async function load(): Promise<void> {
  const snapshot = ++generation;
  const data = (await (
    await api(
      "/admin/submissions?status=" + element<HTMLSelectElement>("filter").value,
    )
  ).json()) as Queue;
  if (snapshot !== generation) return;
  role = data.reviewer.role;
  element("who").textContent = data.reviewer.name;
  element("role").textContent =
    role === "admin" ? t("Administrator") : t("Reviewer");
  clearImages();
  proposals = data.submissions;
  renderQueue();
  void hydrate(snapshot);
}
function review(s: Proposal): void {
  element("review-title").textContent = s.name;
  element("review-id").textContent = s.application_id;
  const content = element("review-content");
  content.replaceChildren();
  const previews = node("div", "", "previews");
  for (const [title, src] of [
    [t("Submitted icon"), images.get(s.id)],
    [
      t("In catalog"),
      s.existing_digest
        ? "/v1/assets/" + s.existing_digest + ".png"
        : undefined,
    ],
  ]) {
    const box = node("div", "", "preview");
    const artwork = node("div", "", "preview-artwork");
    if (title === t("Submitted icon")) {
      artwork.dataset.iconId = s.id;
      artwork.dataset.previewLabel = title;
    }
    if (src) {
      const img = node("img");
      img.alt = title ?? "";
      img.src = src;
      artwork.append(img);
    } else {
      artwork.textContent =
        title === t("In catalog") ? t("No icon") : t("Preview unavailable");
    }
    box.append(artwork);
    box.append(node("p", title ?? ""));
    previews.append(box);
  }
  content.append(previews);
  const facts = node("dl", "", "facts");
  const fact = (label: string, value: string): void => {
    facts.append(node("dt", label), node("dd", value || t("Not provided")));
  };
  fact(t("Variant"), s.variant === "default" ? t("Default") : s.variant);
  fact(t("License"), s.license);
  facts.append(node("dt", t("Source")));
  const source = node("dd");
  try {
    const url = new URL(s.source_url);
    if (url.protocol !== "https:" || url.username || url.password)
      throw Error();
    const link = node("a", url.hostname + " ↗");
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    source.append(link);
  } catch {
    source.textContent = s.source_url || t("Not provided");
  }
  facts.append(source);
  fact(t("Received"), date(s.created_at));
  fact(t("Same icon"), t("Contributions: {count}", { count: s.duplicates }));
  if (s.reason) fact(t("Last decision"), s.reason);
  content.append(facts);
  if (!s.source_url || !s.license || s.license === "unknown")
    content.append(
      node(
        "p",
        t("Check the source and redistribution permission before publishing."),
        "notice",
      ),
    );
  const actions = element("review-actions");
  actions.replaceChildren();
  for (const action of (["pending", "correction"].includes(s.status)
    ? ["approve", "correction", "reject", "merge"]
    : []
  ).concat(
    role === "admin" && !["revoked", "withdrawn"].includes(s.status)
      ? ["revoke"]
      : [],
  )) {
    const b = node(
      "button",
      labels()[action] ?? action,
      action === "approve" ? "primary" : action === "revoke" ? "danger" : "",
    );
    b.onclick = () => decide(s, action);
    actions.append(b);
  }
  element<HTMLDialogElement>("review").showModal();
}
let submitDecision: (() => Promise<void>) | undefined;
function openDecision(
  title: string,
  description: string,
  submit: () => Promise<void>,
  s?: Proposal,
  merge = false,
): void {
  element("decision-title").textContent = title;
  element("decision-description").textContent = description;
  element<HTMLInputElement>("reason").value = "";
  element<HTMLInputElement>("target").value = "";
  element("target-label").hidden = !merge;
  element<HTMLInputElement>("target").required = merge;
  element("metadata").hidden = !s;
  element<HTMLInputElement>("source").value = s?.source_url ?? "";
  element<HTMLInputElement>("license").value =
    s?.license === "unknown" ? "" : (s?.license ?? "");
  element<HTMLInputElement>("source").required = !!s;
  element<HTMLInputElement>("license").required = !!s;
  element("decision-error").textContent = "";
  submitDecision = submit;
  element<HTMLDialogElement>("decision").showModal();
}
function decide(s: Proposal, action: string): void {
  openDecision(
    `${labels()[action] ?? action} · ${s.name}`,
    action === "revoke"
      ? t("Stop distributing this icon. Keep the decision in history.")
      : action === "approve"
        ? t("Publish this icon. Check its source and license first.")
        : t("Record the reason with this contribution."),
    async () => {
      await api(
        "/admin/submissions/" + encodeURIComponent(s.id) + "/decision",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action,
            version: s.version,
            reason: element<HTMLInputElement>("reason").value.trim(),
            targetApplicationId:
              element<HTMLInputElement>("target").value.trim(),
            ...(["approve", "merge"].includes(action)
              ? {
                  sourceUrl: element<HTMLInputElement>("source").value.trim(),
                  license: element<HTMLInputElement>("license").value.trim(),
                }
              : {}),
          }),
        },
      );
      element<HTMLDialogElement>("review").close();
    },
    ["approve", "merge"].includes(action) ? s : undefined,
    action === "merge",
  );
}
element<HTMLFormElement>("decision-form").onsubmit = async (e) => {
  e.preventDefault();
  const confirm = element<HTMLButtonElement>("confirm"),
    cancel = element<HTMLButtonElement>("cancel-decision");
  confirm.disabled = cancel.disabled = true;
  confirm.textContent = t("Saving…");
  try {
    await submitDecision?.();
    element<HTMLDialogElement>("decision").close();
    await refresh();
    say(t("Decision saved."));
  } catch (e) {
    element("decision-error").textContent = message(e);
  } finally {
    confirm.disabled = cancel.disabled = false;
    confirm.textContent = t("Confirm decision");
  }
};
element<HTMLDialogElement>("decision").oncancel = (e) => {
  if (element<HTMLButtonElement>("confirm").disabled) e.preventDefault();
};
element("cancel-decision").onclick = () =>
  element<HTMLDialogElement>("decision").close();
element("close-review").onclick = () =>
  element<HTMLDialogElement>("review").close();
async function records(): Promise<void> {
  const root = element("details");
  if (view === "history") {
    const reviews = (await (await api("/admin/reviews")).json()) as Review[];
    root.replaceChildren();
    if (!reviews.length)
      root.append(
        empty(
          t("No decisions yet."),
          t("Decisions and their reasons appear here."),
        ),
      );
    for (const r of reviews) {
      const row = node("article", "", "record"),
        body = node("div");
      body.append(
        node(
          "strong",
          labels()[r.decision] ??
            labels()[r.operation] ??
            r.decision ??
            r.operation,
        ),
        node("p", r.reason),
        node("small", `${r.reviewer} · ${date(r.created_at)}`),
      );
      if (r.application_name) body.prepend(node("p", r.application_name));
      if (r.application_id) body.append(node("p", r.application_id, "app-id"));
      row.append(body);
      root.append(row);
    }
  } else {
    const revisions = (await (
      await api("/admin/revisions")
    ).json()) as Revision[];
    root.replaceChildren();
    if (!revisions.length)
      root.append(
        empty(
          t("No catalog versions yet."),
          t("The first publication creates a catalog version."),
        ),
      );
    for (const [i, r] of revisions.entries()) {
      const row = node("article", "", "record"),
        body = node("div");
      body.append(
        node("strong", t("Version {version}", { version: r.id })),
        node("p", date(r.created_at)),
      );
      row.append(body);
      if (i === 0) row.append(node("span", t("Latest"), "badge"));
      if (role === "admin") {
        const b = node("button", t("Restore"));
        b.onclick = () =>
          openDecision(
            t("Restore version {version}", { version: r.id }),
            t(
              "Create a version from this snapshot. Revoked icons remain blocked.",
            ),
            async () => {
              await api("/admin/rollback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  revision: r.id,
                  reason: element<HTMLInputElement>("reason").value.trim(),
                }),
              });
            },
          );
        row.append(b);
      }
      root.append(row);
    }
  }
}
async function refresh(): Promise<void> {
  const button = element<HTMLButtonElement>("refresh");
  button.disabled = true;
  say("");
  const root = element(view === "inbox" ? "queue" : "details");
  root.setAttribute("aria-busy", "true");
  root.replaceChildren(
    ...Array.from({ length: LOADING_PLACEHOLDER_COUNT }, () =>
      node("div", "", "skeleton"),
    ),
  );
  try {
    if (view === "inbox") await load();
    else await records();
  } catch (e) {
    root.replaceChildren(empty(t("Could not load."), message(e)));
    say(t("Select Refresh to retry."), true);
  } finally {
    button.disabled = false;
    root.removeAttribute("aria-busy");
  }
}
for (const id of ["inbox", "history", "revisions"])
  element(id).onclick = () => {
    if (element<HTMLButtonElement>("refresh").disabled) return;
    view = id;
    generation++;
    for (const nav of ["inbox", "history", "revisions"]) {
      element(nav).removeAttribute("aria-current");
    }
    element(id).setAttribute("aria-current", "page");
    element("page-title").textContent =
      id === "inbox"
        ? t("Review queue")
        : id === "history"
          ? t("Decision history")
          : t("Catalog versions");
    element("page-subtitle").textContent =
      id === "inbox"
        ? t("Review submitted icons.")
        : id === "history"
          ? t("Decisions and reasons.")
          : t("Inspect or restore catalog versions.");
    element("toolbar").hidden = element("queue").hidden = id !== "inbox";
    element("details").hidden = id === "inbox";
    void refresh();
  };
element<HTMLFormElement>("login").onsubmit = async (e) => {
  e.preventDefault();
  const button = element<HTMLButtonElement>("unlock");
  button.disabled = true;
  button.textContent = t("Signing in…");
  element("login-error").textContent = "";
  token = element<HTMLInputElement>("token").value.trim();
  try {
    await load();
    element<HTMLInputElement>("token").value = "";
    element("login-screen").hidden = true;
    element("workspace").hidden = false;
    element("page-title").tabIndex = -1;
    element("page-title").focus();
    if (suspendedReview) element<HTMLDialogElement>("review").showModal();
    if (suspendedDecision) {
      element("decision-error").textContent = t(
        "Access renewed. Review your draft before confirming.",
      );
      element<HTMLDialogElement>("decision").showModal();
    }
    suspendedReview = suspendedDecision = false;
  } catch (e) {
    token = "";
    element("login-error").textContent = message(e);
  } finally {
    button.disabled = false;
    button.textContent = t("Sign in");
  }
};
element("reveal").onclick = () => {
  const input = element<HTMLInputElement>("token");
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  element("reveal").setAttribute(
    "aria-label",
    show ? t("Hide password") : t("Show password"),
  );
  element("reveal").setAttribute("aria-pressed", String(show));
};
element("logout").onclick = () => {
  token = "";
  clearImages();
  location.reload();
};
element("refresh").onclick = () => void refresh();
element("filter").onchange = () => void refresh();
element("search").oninput = () => renderQueue();
