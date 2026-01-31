const $ = (id) => document.getElementById(id);

function badgeClass(status){
  if(status === "DONE") return "good";
  if(status === "ERROR") return "bad";
  if(status === "RUNNING") return "warn";
  return "";
}

function safeTitle(a){
  return a.title || `${a.kind.toUpperCase()} • ${a.id.slice(0,8)}`;
}

async function api(path, opts={}){
  const res = await fetch(path, opts);
  if(!res.ok){
    const txt = await res.text();
    throw new Error(txt || res.statusText);
  }
  return res.json();
}

async function refresh(){
  const q = $("searchInput").value.trim();
  const status = $("statusInput").value;
  const params = new URLSearchParams();
  if(q) params.set("q", q);
  if(status) params.set("status", status);

  const list = await api(`/api/archives?${params.toString()}`);
  const el = $("list");
  el.innerHTML = "";

  if(list.length === 0){
    el.innerHTML = `<div class="meta">No results.</div>`;
    return;
  }

  for(const a of list){
    const item = document.createElement("div");
    item.className = "item";

    const left = document.createElement("div");
    left.className = "left";

    const title = document.createElement("div");
    title.className = "title";
    title.textContent = safeTitle(a);

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `${a.status} • ${a.kind} • ${a.url}`;

    left.appendChild(title);
    left.appendChild(meta);

    const right = document.createElement("div");
    right.className = "actions";

    const badge = document.createElement("div");
    badge.className = `badge ${badgeClass(a.status)}`;
    badge.textContent = a.status;

    right.appendChild(badge);

    if(a.status === "DONE"){
      const dl = document.createElement("a");
      dl.href = `/api/archive/${a.id}/download`;
      dl.textContent = "Download";
      right.appendChild(dl);
    }

    if(a.status === "ERROR"){
      const err = document.createElement("a");
      err.href = "#";
      err.textContent = "Details";
      err.onclick = async (e) => {
        e.preventDefault();
        const full = await api(`/api/archive/${a.id}`);
        alert(full.error || "Unknown error");
      };
      right.appendChild(err);
    }

    item.appendChild(left);
    item.appendChild(right);
    el.appendChild(item);
  }
}

$("refreshBtn").addEventListener("click", refresh);
$("searchInput").addEventListener("keydown", (e)=>{ if(e.key==="Enter") refresh(); });
$("statusInput").addEventListener("change", refresh);

$("submitForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("submitMsg").textContent = "Queueing…";

  const url = $("urlInput").value.trim();
  const kind = $("kindInput").value;

  try{
    await api("/api/archive", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({url, kind: kind || null})
    });
    $("submitMsg").textContent = "Queued. Refresh in a few seconds.";
    $("urlInput").value = "";
    await refresh();
  }catch(err){
    $("submitMsg").textContent = `Error: ${err.message}`;
  }
});

refresh();
setInterval(refresh, 8000);
