const form = document.getElementById("archiveForm");
const urlInput = document.getElementById("urlInput");
const kindSelect = document.getElementById("kindSelect");
const statusEl = document.getElementById("status");
const listEl = document.getElementById("list");
const searchInput = document.getElementById("searchInput");
const statusSelect = document.getElementById("statusSelect");
const refreshBtn = document.getElementById("refreshBtn");

const modal = document.getElementById("modal");
const modalTitle = document.getElementById("modalTitle");
const modalBody = document.getElementById("modalBody");

let refreshing = false;

function openModal(title, body) {
  modalTitle.textContent = title || "Details";
  modalBody.textContent = body || "";
  modal.setAttribute("aria-hidden", "false");
}
function closeModal() {
  modal.setAttribute("aria-hidden", "true");
}

modal.addEventListener("click", (e) => {
  if (e.target.matches("[data-close]")) closeModal();
});
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

function setStatus(html) {
  statusEl.innerHTML = html || "";
}

function escapeHtml(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function tryHost(url) {
  try { return new URL(url).host; } catch { return url; }
}

function fmtTime(iso) {
  try { return new Date(iso).toLocaleString(); } catch { return iso || ""; }
}

function statusPill(s) {
  const st = (s || "").toUpperCase();
  if (st === "DONE") return `<span class="pill good"><span class="dot"></span>DONE</span>`;
  if (st === "ERROR") return `<span class="pill bad"><span class="dot"></span>ERROR</span>`;
  if (st === "RUNNING") return `<span class="pill run"><span class="dot"></span>RUNNING</span>`;
  if (st === "QUEUED") return `<span class="pill warn"><span class="dot"></span>QUEUED</span>`;
  return `<span class="pill"><span class="dot"></span>${escapeHtml(st || "UNKNOWN")}</span>`;
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const ct = (res.headers.get("content-type") || "").toLowerCase();
  const isJson = ct.includes("application/json");

  let body;
  try { body = isJson ? await res.json() : await res.text(); }
  catch { body = isJson ? null : ""; }

  if (!res.ok) {
    let msg = res.statusText || "Request failed";
    if (body && typeof body === "object") msg = body.detail || body.error || JSON.stringify(body);
    else if (typeof body === "string" && body.trim()) msg = body.trim();
    throw new Error(msg);
  }
  return body;
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;

  try {
    const params = new URLSearchParams();
    const q = (searchInput.value || "").trim();
    const status = (statusSelect.value || "").trim();
    if (q) params.set("q", q);
    if (status) params.set("status", status);

    const qs = params.toString();
    const data = await api(`/api/archives${qs ? "?" + qs : ""}`);

    if (!Array.isArray(data) || data.length === 0) {
      listEl.innerHTML = `<div class="empty">No archives yet. Add one on the left.</div>`;
      return;
    }

    listEl.innerHTML = data.map(renderItem).join("");
  } catch (e) {
    listEl.innerHTML = `<div class="empty">Can't load archives. Check the API logs.</div>`;
    openModal("Refresh failed", String(e?.message || e));
  } finally {
    refreshing = false;
  }
}

function renderItem(a) {
  const id = escapeHtml(a.id);
  const kind = escapeHtml(a.kind || "page");
  const url = escapeHtml(a.url || "");
  const host = escapeHtml(tryHost(a.url || ""));
  const created = escapeHtml(fmtTime(a.created_at));
  const title = escapeHtml(a.title || host || a.id);

  const downloadBtn =
    (a.status || "").toUpperCase() === "DONE"
      ? `<a class="btn small" href="/api/archive/${id}/download" target="_blank" rel="noreferrer">Download</a>`
      : `<button class="btn small" type="button" disabled>Download</button>`;

  return `
    <div class="item">
      <div class="kind" data-kind="${kind}">${kind.toUpperCase()}</div>

      <div class="item-main">
        <div class="item-title">${title}</div>
        <div class="item-meta">
          ${statusPill(a.status)}
          <span class="chip">${created}</span>
          <span class="chip">${host}</span>
        </div>
        <div class="item-meta" style="margin-top:8px">
          <span class="muted">URL:</span> <span>${url}</span>
        </div>
      </div>

      <div class="item-actions">
        ${downloadBtn}
        <button class="btn small" type="button" data-details="${id}">Details</button>
      </div>
    </div>
  `;
}

listEl.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-details]");
  if (!btn) return;

  const id = btn.getAttribute("data-details");
  try {
    const a = await api(`/api/archive/${encodeURIComponent(id)}`);
    openModal(`Archive ${id}`, JSON.stringify(a, null, 2));
  } catch (err) {
    openModal("Details failed", String(err?.message || err));
  }
});

refreshBtn.addEventListener("click", refresh);
searchInput.addEventListener("input", () => {
  clearTimeout(searchInput._t);
  searchInput._t = setTimeout(refresh, 200);
});
statusSelect.addEventListener("change", refresh);

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const url = (urlInput.value || "").trim();
  if (!url) return;

  const kind = (kindSelect.value || "").trim() || null;

  try {
    setStatus(`<span class="spin"></span>Queued…`);
    const res = await api("/api/archive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, kind }),
    });

    setStatus(`<span class="ok">Queued:</span> <span class="chip">${escapeHtml(res.id)}</span>`);
    urlInput.value = "";
    kindSelect.value = "";
    await refresh();
  } catch (err) {
    setStatus(`<span class="bad">Error:</span> ${escapeHtml(err?.message || err)}`);
    openModal("Archive failed", String(err?.message || err));
  }
});

setInterval(refresh, 8000);
refresh();
