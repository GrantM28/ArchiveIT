const $ = (s) => document.querySelector(s);

const els = {
  url: $("#url"),
  kind: $("#kind"),
  go: $("#go"),
  refresh: $("#refresh"),
  toggleAuto: $("#toggleAuto"),
  list: $("#list"),
  empty: $("#empty"),
  toasts: $("#toasts"),
  apiStatus: $("#apiStatus"),
  search: $("#search"),
  filter: $("#filter"),
  statTotal: $("#statTotal"),
  statActive: $("#statActive"),
  statDone: $("#statDone"),
};

let autoOn = true;
let autoTimer = null;
let lastData = [];

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[m]));
}

function toast(title, msg, type = "good") {
  const div = document.createElement("div");
  div.className = `toast ${type}`;
  div.innerHTML = `<div class="toast__title">${escapeHtml(title)}</div>
                   <div class="toast__msg">${escapeHtml(msg)}</div>`;
  els.toasts.appendChild(div);
  setTimeout(() => div.remove(), 3200);
}

async function api(path, { method = "GET", body } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(path, opts);
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }

  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return data;
}

function kindEmoji(kind) {
  return kind === "video" ? "🎥" : "📰";
}

function setApiPill(ok, msg) {
  els.apiStatus.classList.toggle("good", ok);
  els.apiStatus.classList.toggle("bad", !ok);
  els.apiStatus.textContent = ok ? `API: OK` : `API: ${msg}`;
}

function setLoading(on) {
  els.go.classList.toggle("is-loading", on);
  els.go.disabled = on;
}

function computeStats(rows) {
  const total = rows.length;
  const active = rows.filter(r => r.status === "PENDING" || r.status === "RUNNING").length;
  const done = rows.filter(r => r.status === "DONE").length;
  els.statTotal.textContent = total;
  els.statActive.textContent = active;
  els.statDone.textContent = done;
}

function applyFilters(rows) {
  const q = (els.search.value || "").trim().toLowerCase();
  const f = els.filter.value;

  return rows.filter(r => {
    if (f !== "all" && r.status !== f) return false;
    if (!q) return true;
    return (r.title || "").toLowerCase().includes(q) || (r.url || "").toLowerCase().includes(q);
  });
}

function render(rows) {
  computeStats(rows);

  const filtered = applyFilters(rows);
  els.list.innerHTML = "";

  if (!filtered.length) {
    els.empty.hidden = rows.length !== 0; // show "empty" only when there are truly none
    if (rows.length !== 0) {
      els.empty.hidden = false;
      els.empty.querySelector(".empty__icon").textContent = "🔎";
      els.empty.querySelector(".empty__title").textContent = "No matches";
      els.empty.querySelector(".empty__sub").textContent = "Try a different search or filter.";
    }
    return;
  }

  els.empty.hidden = true;

  for (const r of filtered) {
    const item = document.createElement("div");
    item.className = "item";

    const title = r.title || "(untitled)";
    const url = r.url || "";
    const status = r.status || "PENDING";
    const kind = r.kind || "article";

    const canDownload = status === "DONE" && r.primary_path;

    item.innerHTML = `
      <div class="item__left">
        <div class="badgeKind" title="${escapeHtml(kind)}">${kindEmoji(kind)}</div>
        <div class="item__meta">
          <div class="item__title" title="${escapeHtml(title)}">${escapeHtml(title)}</div>
          <div class="item__url" title="${escapeHtml(url)}">${escapeHtml(url)}</div>
        </div>
      </div>
      <div class="item__right">
        <span class="status ${escapeHtml(status)}">${escapeHtml(status)}</span>
        <button class="smallBtn" data-act="reprocess" title="Re-run capture">Reprocess</button>
        <button class="smallBtn" data-act="open" title="Open original URL">Open</button>
        <button class="smallBtn" data-act="download" ${canDownload ? "" : "disabled"} title="Download archive">Download</button>
        <button class="smallBtn danger" data-act="delete" title="Delete record">Delete</button>
      </div>
    `;

    item.addEventListener("click", async (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;

      const act = btn.dataset.act;
      try {
        if (act === "open") {
          window.open(url, "_blank", "noopener,noreferrer");
          return;
        }

        if (act === "download") {
          if (!canDownload) return;
          window.location.href = `/api/archive/${r.id}/download`;
          return;
        }

        if (act === "reprocess") {
          btn.disabled = true;
          await api(`/api/archive/${r.id}/process`, { method: "POST" });
          toast("Queued", "Reprocess started.", "good");
          await refresh();
          return;
        }

        if (act === "delete") {
          if (!confirm(`Delete archive #${r.id}?`)) return;
          btn.disabled = true;
          await api(`/api/archive/${r.id}`, { method: "DELETE" });
          toast("Deleted", "Archive removed.", "good");
          await refresh();
          return;
        }
      } catch (err) {
        toast("Error", err.message || String(err), "bad");
      } finally {
        btn.disabled = false;
      }
    });

    els.list.appendChild(item);
  }
}

async function refresh() {
  try {
    const rows = await api("/api/archives");
    lastData = Array.isArray(rows) ? rows : [];
    setApiPill(true);
    render(lastData);
  } catch (err) {
    setApiPill(false, err.message || "down");
    // Don't spam alerts; just keep UI calm.
    console.error(err);
  }
}

async function createArchive() {
  const url = (els.url.value || "").trim();
  const kind = els.kind.value;

  if (!url) {
    toast("Missing URL", "Paste a website link first.", "bad");
    els.url.focus();
    return;
  }

  setLoading(true);
  try {
    await api("/api/archive", { method: "POST", body: { url, kind } });
    toast("Queued", "Capture job queued.", "good");
    els.url.value = "";
    await refresh();
  } catch (err) {
    toast("Failed", err.message || String(err), "bad");
  } finally {
    setLoading(false);
  }
}

function setAuto(on) {
  autoOn = on;
  els.toggleAuto.dataset.on = on ? "1" : "0";
  els.toggleAuto.textContent = `Auto refresh: ${on ? "On" : "Off"}`;

  if (autoTimer) clearInterval(autoTimer);
  if (on) autoTimer = setInterval(() => refresh(), 2500);
}

els.go.addEventListener("click", createArchive);
els.refresh.addEventListener("click", () => refresh());
els.toggleAuto.addEventListener("click", () => setAuto(!autoOn));
els.search.addEventListener("input", () => render(lastData));
els.filter.addEventListener("change", () => render(lastData));

els.url.addEventListener("keydown", (e) => {
  if (e.key === "Enter") createArchive();
});

setAuto(true);
refresh();
