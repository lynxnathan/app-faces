import { adminStyles } from "./admin.styles";
import adminScript from "../build/admin.bundle.txt";

export const dashboard = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <meta name="theme-color" content="#100c14" />
    <title>App Faces · Moderation</title>
    <style>
      ${adminStyles}
    </style>
  </head>
  <body>
    <main id="login-screen" class="login-screen">
      <section class="login-card" aria-label="Sign in">
        <div class="brand login-brand">
          <span class="mark" role="img" aria-label="App Faces"></span>
        </div>
        <form id="login">
          <label for="token">Access password</label>
          <div class="password-wrap">
            <input
              id="token"
              type="password"
              dir="ltr"
              autocomplete="current-password"
              autocapitalize="none"
              required
              spellcheck="false"
              aria-describedby="login-error"
            />
            <button type="button" id="reveal" aria-label="Show password" aria-pressed="false">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
                <circle cx="12" cy="12" r="3" />
                <path class="eye-slash" d="m3 3 18 18" />
              </svg>
            </button>
          </div>
          <p id="login-error" class="notice error" role="alert"></p>
          <button class="primary" id="unlock" type="submit">
            Sign in
          </button>
        </form>
      </section>
    </main>
    <section id="workspace" class="shell" hidden>
      <header class="workspace-header">
        <div class="header-content">
          <div class="brand">
            <span class="mark" aria-hidden="true"></span>App Faces
          </div>
          <div class="account">
            <div class="account-identity"><strong id="who"></strong><span id="role"></span></div>
            <button id="logout">Sign out ↗</button>
          </div>
        </div>
        <nav aria-label="Main navigation">
          <button id="inbox" aria-current="page">Review queue</button>
          <button id="history">History</button>
          <button id="revisions">Catalog versions</button>
        </nav>
      </header>
      <main class="main">
        <div class="page-heading">
          <div>
            <h1 id="page-title">Review queue</h1>
            <p id="page-subtitle">Review submitted icons.</p>
          </div>
          <button id="refresh" aria-label="Refresh data">↻ Refresh</button>
        </div>
        <p id="message" class="notice" role="status" aria-live="polite"></p>
        <div class="toolbar" id="toolbar">
          <input
            id="search"
            class="search"
            type="search"
            aria-label="Search this queue"
            placeholder="Search name or application…"
          /><select id="filter" aria-label="Contribution status">
            <option value="pending">Pending</option>
            <option value="correction">Correction requested</option>
            <option value="approved">Approved</option>
            <option value="merged">Merged</option>
            <option value="rejected">Rejected</option>
            <option value="withdrawn">Withdrawn</option>
            <option value="revoked">Revoked</option></select
          ><span id="count" class="count"></span>
        </div>
        <section id="queue" class="panel" aria-label="Contributions"></section>
        <section id="details" class="panel" hidden></section>
      </main>
    </section>
    <dialog id="review" class="review-dialog" aria-labelledby="review-title">
      <div class="dialog-body">
        <div class="dialog-header">
          <div>
            <div class="eyebrow">Contribution review</div>
            <h2 id="review-title" dir="auto"></h2>
            <p id="review-id" dir="ltr" class="app-id"></p>
          </div>
          <button id="close-review" class="close" aria-label="Close review">
            ×
          </button>
        </div>
        <div id="review-content"></div>
      </div>
      <div id="review-actions" class="review-actions"></div>
    </dialog>
    <dialog id="decision" aria-labelledby="decision-title">
      <form id="decision-form">
        <div class="dialog-body">
          <h2 id="decision-title"></h2>
          <p id="decision-description"></p>
          <label for="reason">Decision reason</label
          ><textarea
            id="reason" dir="auto"
            required
            maxlength="1000"
            placeholder="Enter a reason for future reviews."
          ></textarea>
          <div id="target-label" hidden>
            <label for="target">Target application ID</label
            ><input
              id="target" dir="ltr"
              maxlength="160"
              placeholder="org.example.Application"
            />
          </div>
          <div id="metadata" hidden>
            <label for="source">Icon source</label
            ><input id="source" dir="ltr" type="url" placeholder="https://…" /><label
              for="license"
              >License or redistribution permission</label
            ><input id="license" maxlength="300" />
          </div>
          <p id="decision-error" class="notice error" role="alert"></p>
        </div>
        <div class="dialog-footer">
          <button type="button" id="cancel-decision">Cancel</button
          ><button class="primary" id="confirm">Confirm decision</button>
        </div>
      </form>
    </dialog>
    <script>
      ${adminScript};
    </script>
  </body>
</html>
`;
