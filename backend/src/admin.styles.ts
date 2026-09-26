export const adminStyles = `:root {
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;
  color-scheme: dark;
  font-synthesis: none;
  --page: #100c14;
  --surface: #1b1421;
  --raised: #251b2d;
  --field: #140f19;
  --text: #f6edf4;
  --muted: #bfadc2;
  --line: #453249;
  --control-line: #8c718d;
  --accent: #d6b5ff;
  --gold: #e4c18b;
  --action: #8c2756;
  --action-hover: #a13267;
  --danger: #ff9bac;
  --artwork-ink: #544559;
  color: var(--text);
  background: var(--page);
}
* {
  box-sizing: border-box;
}
[hidden] {
  display: none !important;
}
body {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
}
button,
input,
select,
textarea {
  font: inherit;
}
button {
  cursor: pointer;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
  padding: 10px 15px;
  min-height: 44px;
  font-weight: 600;
  box-shadow: 0 1px 2px #0003;
  transition:
    background 0.15s,
    box-shadow 0.15s;
}
button:hover {
  background: var(--raised);
  box-shadow: 0 3px 12px #0004;
}
button:disabled {
  opacity: 0.55;
  cursor: wait;
}
.primary {
  background: linear-gradient(110deg, var(--action), #702967);
  color: #fff;
  border-color: #b75c88;
}
.primary:hover {
  background: var(--action-hover);
}
.danger {
  color: var(--danger);
}
input,
select,
textarea {
  border: 1px solid var(--control-line);
  background: var(--surface);
  border-radius: 10px;
  padding: 11px 12px;
  color: var(--text);
  max-width: 100%;
  width: 100%;
}
textarea {
  resize: vertical;
  min-height: 95px;
}
input::placeholder, textarea::placeholder { color: var(--muted); opacity: 1; }
::selection { background: #734569; color: #fff; }
input:focus,
textarea:focus,
select:focus {
  border-color: var(--accent);
}
:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}
label {
  display: block;
  font-weight: 600;
  margin: 20px 0 7px;
}
h1,
h2,
h3,
p {
  margin-top: 0;
}
h1 {
  font-family: Georgia, "Times New Roman", serif;
  font-weight: 400;
  font-size: 38px;
  letter-spacing: -1px;
  line-height: 1.2;
}
h2 {
  font-size: 23px;
  letter-spacing: -0.6px;
}
h3 {
  font-size: 15px;
}
p {
  color: var(--muted);
}
a {
  color: var(--accent);
  text-underline-offset: 3px;
  overflow-wrap: anywhere;
}
.brand {
  display: flex;
  gap: 11px;
  align-items: center;
  font-size: 21px;
  font-weight: 750;
  letter-spacing: -0.7px;
  color: var(--text);
}
.mark {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(145deg, #a53562, #622865);
  border: 1px solid #d290aa66;
  display: inline-grid;
  place-content: center;
  color: white;
  box-shadow: 0 4px 20px #b6287540, inset 0 1px 0 #ffffff29;
}
.mark:after {
  content: "a";
  font-size: 29px;
  line-height: 1;
  font-weight: 800;
  transform: translateY(-2px);
}
.eyebrow {
  font-size: 11px;
  font-weight: 750;
  letter-spacing: 1.6px;
  text-transform: uppercase;
  color: var(--gold);
  margin-bottom: 18px;
}
.muted {
  color: var(--muted);
}
.login-screen {
  min-height: 100svh;
  display: grid;
  place-items: center;
  padding: 32px 20px;
  background:
    radial-gradient(ellipse at 25% 15%, #5e153b55, transparent 55%),
    radial-gradient(ellipse at 80% 85%, #4e28704a, transparent 50%),
    var(--page);
}
.login-card {
  width: min(100%, 440px);
  padding: 40px;
  border: 1px solid transparent;
  border-radius: 24px;
  background:
    linear-gradient(145deg, #271827, var(--surface) 60%) padding-box,
    linear-gradient(145deg, #c19075, #603250 40%, #45364f 75%, #8e6898) border-box;
  box-shadow: 0 32px 100px -24px #000c, 0 0 80px -48px #b62875;
}
.login-brand {
  justify-content: center;
  margin-bottom: 32px;
  font-size: 22px;
}
.login-brand .mark {
  width: 56px;
  height: 56px;
  border-radius: 16px;
}
.login-brand .mark:after { font-size: 40px; }
#reveal { display: grid; place-items: center; }
.eye-slash { display: none; }
#reveal[aria-pressed="true"] .eye-slash { display: block; }
.login-card label {
  margin-top: 0;
  margin-bottom: 9px;
}
.password-wrap {
  display: flex;
  align-items: center;
  min-height: 52px;
  border: 1px solid var(--control-line);
  border-radius: 12px;
  background: var(--field);
  padding: 4px;
  gap: 4px;
}
.password-wrap:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px #d6b5ff33;
}
.password-wrap input {
  min-width: 0;
  flex: 1;
  border: 0;
  background: transparent;
  padding: 9px 10px;
  font-size: 16px;
  outline: none;
}
.password-wrap button {
  position: static;
  flex-shrink: 0;
  min-height: 44px;
  min-width: 52px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  box-shadow: none;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--muted);
}
.password-wrap button:hover {
  background: var(--raised);
}
#unlock {
  width: 100%;
  min-height: 52px;
  margin-top: 20px;
  border-radius: 12px;
  font-size: 15px;
  box-shadow: 0 6px 24px #8c275640, inset 0 1px 0 #ffffff24;
}
#unlock:active {
  box-shadow: none;
}
.shell {
  min-height: 100svh;
  background:
    radial-gradient(ellipse at 0 0, #4e183535, transparent 65%),
    var(--page);
}
.workspace-header {
  background: linear-gradient(100deg, #271421, #18121e 65%);
  border-bottom: 1px solid var(--line);
}
.header-content,
.workspace-header nav,
.main {
  width: min(100%, 1120px);
  margin-inline: auto;
  padding-inline: 32px;
}
.header-content {
  min-height: 100px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
}
.account {
  display: flex;
  gap: 20px;
  align-items: center;
  min-width: 0;
}
.account-identity {
  display: grid;
  text-align: end;
  font-size: 12px;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.account strong { color: var(--text); }
.account button { flex-shrink: 0; }
.workspace-header nav {
  display: flex;
  gap: 28px;
  overflow-x: auto;
}
nav button {
  border: 0;
  border-bottom: 3px solid transparent;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  color: var(--muted);
  padding: 16px 2px;
  white-space: nowrap;
}
nav button:hover { background: transparent; box-shadow: none; color: var(--accent); }
nav button[aria-current="page"] { border-bottom-color: var(--accent); color: var(--accent); }
nav button:focus-visible { outline-offset: -3px; border-radius: 6px; }
.main { min-width: 0; padding-block: 0 64px; }
.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 44px 0 32px;
  gap: 20px;
}
.page-heading > button { white-space: nowrap; flex-shrink: 0; }
.page-heading h1 {
  font-family: Georgia, "Times New Roman", serif;
  font-weight: 400;
  margin-bottom: 8px;
}
.page-heading p {
  margin: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.search {
  max-width: 320px;
}
.toolbar select {
  width: 190px;
}
.count {
  margin-inline-start: auto;
  font-size: 12px;
  color: var(--muted);
}
.panel {
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--surface);
  overflow: hidden;
  box-shadow: 0 16px 48px -24px #000a;
}
.list-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 120px 150px;
  gap: 15px;
  padding: 13px 24px;
  background: var(--raised);
  border-bottom: 1px solid var(--line);
  font-size: 11px;
  font-weight: 650;
  color: var(--muted);
}
.proposal {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 120px 150px;
  gap: 15px;
  align-items: center;
  text-align: start;
  border: 0;
  border-bottom: 1px solid var(--line);
  border-radius: 0;
  box-shadow: none;
  padding: 20px 24px;
  font-weight: 400;
}
.proposal:last-child {
  border-bottom: 0;
}
.proposal:hover {
  background: #302137;
}
.app-cell {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}
.icon-well {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  background: #eee8ee;
  border: 1px solid #fff2;
  border-radius: 12px;
  overflow: hidden;
  color: var(--artwork-ink);
  font-size: 21px;
}
.icon-well img {
  width: 36px;
  height: 36px;
  object-fit: contain;
}
.app-cell > span:last-child { min-width: 0; overflow-wrap: anywhere; }
.app-cell strong {
  display: block;
  font-size: 14px;
}
.app-id {
  display: block;
  color: var(--muted);
  font-size: 12px;
  overflow-wrap: anywhere;
  font-weight: 400;
}
.badge {
  display: inline-block;
  border-radius: 5px;
  padding: 3px 8px;
  background: #332536;
  color: var(--gold);
  font-size: 11px;
  font-weight: 600;
  width: fit-content;
}
.date {
  font-size: 12px;
  color: var(--muted);
}
.empty {
  padding: 80px 25px;
  text-align: center;
}
.empty h2 {
  font-size: 19px;
}
.empty p {
  max-width: 340px;
  margin: 0 auto;
  line-height: 1.8;
}
.notice {
  border-radius: 10px;
  padding: 12px 15px;
  background: #162e29;
  color: #a6dfc8;
  font-size: 13px;
  margin: 0 0 20px;
}
.notice:empty {
  display: none;
}
.error {
  background: #391b2b;
  color: var(--danger);
}
.error:empty {
  display: none;
}
#login-error {
  margin-top: 16px;
  margin-bottom: 0;
}
dialog {
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 0;
  width: 510px;
  max-width: calc(100vw - 32px);
  max-height: calc(100svh - 32px);
  color: var(--text);
  background: var(--surface);
  box-shadow: 0 32px 100px #000b;
}
dialog[open] {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
#decision-form {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
dialog::backdrop {
  background: #09060dc9;
  backdrop-filter: blur(3px);
}
.dialog-body {
  padding: 30px;
  overflow-y: auto;
  min-height: 0;
}
.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 18px;
}
.dialog-header h2 {
  margin-bottom: 8px;
}
.close {
  border: 0;
  background: transparent;
  box-shadow: none;
  padding: 3px 9px;
  min-width: 44px;
  flex-shrink: 0;
  font-size: 23px;
  color: var(--muted);
}
.dialog-footer {
  flex-shrink: 0;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  background: var(--raised);
  border-top: 1px solid var(--line);
  padding: 18px 30px;
}
.review-dialog {
  width: 680px;
}
.dialog-header > div { min-width: 0; overflow-wrap: anywhere; }
.dialog-header .eyebrow { margin-bottom: 10px; }
.dialog-header .app-id { margin-bottom: 0; }
.previews {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  margin: 28px 0;
}
.preview {
  border: 1px solid var(--line);
  border-radius: 12px;
  text-align: center;
  background: var(--field);
  padding: 24px 12px 16px;
}
.preview img {
  width: 104px;
  height: 104px;
  object-fit: contain;
}
.preview-artwork {
  height: 144px;
  display: grid;
  place-items: center;
  margin-bottom: 12px;
  border-radius: 8px;
  background-color: #f3eff3;
  background-image: conic-gradient(#e5dfe7 25%, transparent 0 50%, #e5dfe7 0 75%, transparent 0);
  background-size: 16px 16px;
  color: var(--artwork-ink);
  font-size: 13px;
}
.preview p {
  font-size: 12px;
  font-weight: 600;
  margin: 0;
}
.facts {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 15px;
  font-size: 13px;
}
.facts dt {
  color: var(--muted);
}
.facts dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.review-actions {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  flex-shrink: 0;
  gap: 10px;
  padding: 20px 30px;
  border-top: 1px solid var(--line);
  background: var(--raised);
}
.review-actions:empty { display: none; }
.review-actions button { overflow-wrap: anywhere; }
.review-actions .primary { grid-column: 1 / -1; }
.record {
  padding: 22px 26px;
  border-bottom: 1px solid var(--line);
  display: flex;
  gap: 20px;
  align-items: center;
}
.record:last-child {
  border-bottom: 0;
}
.record > div {
  flex: 1;
  min-width: 0;
}
.record strong { overflow-wrap: anywhere; }
.record p {
  font-size: 13px;
  margin: 5px 0 0;
  overflow-wrap: anywhere;
}
.record small {
  color: var(--muted);
}
.skeleton {
  height: 89px;
  margin: 15px 24px;
  border-radius: 8px;
  background: linear-gradient(90deg, var(--surface), #36243d, var(--surface));
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
@keyframes shimmer {
  to {
    background-position: -200% 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  * {
    animation: none !important;
    transition: none !important;
  }
}
@media (max-width: 720px) {
  .login-screen { padding: 24px 16px; }
  .login-card { padding: 32px 24px; border-radius: 20px; }
  .header-content, .workspace-header nav, .main { padding-inline: 20px; }
  .header-content { min-height: 84px; gap: 12px; }
  .brand { font-size: 19px; gap: 8px; }
  .account-identity { display: none; }
  .account button { font-size: 12px; padding-inline: 10px; }
  .workspace-header nav { gap: 20px; }
  nav button { font-size: 13px; }
  .page-heading { margin: 28px 0 24px; align-items: start; gap: 12px; }
  h1 { font-size: 30px; }
  .page-heading > button { font-size: 12px; padding-inline: 10px; }
  .toolbar { flex-wrap: wrap; }
  .search { max-width: none; flex-basis: 100%; }
  .toolbar select { flex: 1; width: auto; min-width: 0; }
  .count { margin: 0; }
  .proposal, .list-head { grid-template-columns: minmax(0, 1fr) 75px; padding: 17px 16px; gap: 8px; }
  .list-head > :last-child, .proposal > .date { display: none; }
  .app-cell { gap: 10px; }
  .app-id { font-size: 11px; }
  .icon-well { width: 40px; height: 40px; border-radius: 10px; }
  .icon-well img { width: 30px; height: 30px; }
  .badge { overflow-wrap: anywhere; max-width: 100%; }
  .dialog-body { padding: 24px 20px; }
  .dialog-footer, .review-actions { padding: 16px 20px; }
  .dialog-footer button { flex: 1; }
  .review-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .review-actions button { padding-inline: 8px; font-size: 13px; }
  .previews { gap: 10px; margin-block: 24px; }
  .preview { padding: 12px 8px; }
  .preview-artwork { height: 112px; }
  .preview img { width: 80px; height: 80px; }
  .facts { grid-template-columns: 85px minmax(0, 1fr); gap: 16px 12px; }
  .record { padding: 20px; flex-wrap: wrap; gap: 12px; }
  .record > div { flex-basis: 100%; }
  .empty { padding: 56px 20px; }
}
`;
