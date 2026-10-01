document.addEventListener("DOMContentLoaded", () => { fetchMe(); fetchRouters(); autoFillPort(); });

async function fetchMe() {
    try {
        const res = await fetch("/api/auth/me");
        if (res.status === 401) return window.location.href = "/login";
        const d = await res.json();
        document.getElementById("currentUsername").textContent = d.username;
    } catch (e) { console.error(e); }
}

async function fetchRouters() {
    try {
        const res = await fetch("/api/routers");
        if (res.status === 401) return window.location.href = "/login";
        const rs = await res.json();
        const grid = document.getElementById("routersGrid");
        const empty = document.getElementById("emptyState");
        grid.innerHTML = "";
        if (!rs.length) return empty.classList.remove("hidden");
        empty.classList.add("hidden");
        rs.forEach(r => grid.appendChild(createRouterCard(r)));
    } catch (e) { console.error(e); }
}

function autoFillPort() {
    document.getElementById("routerPort").value = document.getElementById("routerType").value === "rest" ? 443 : 22;
}

// Modal and state management
function openAddModal() {
    document.getElementById("routerForm").reset();
    autoFillPort();
    document.getElementById("modalError").classList.add("hidden");
    document.getElementById("addModal").classList.remove("hidden");
}

function closeAddModal() { document.getElementById("addModal").classList.add("hidden"); }

document.getElementById("routerForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("saveBtn");
    const errBox = document.getElementById("modalError");
    errBox.classList.add("hidden");
    btn.disabled = true;
    btn.textContent = "Testing...";
    
    const payload = {
        name: document.getElementById("routerName").value,
        host: document.getElementById("routerHost").value,
        port: parseInt(document.getElementById("routerPort").value),
        connection_type: document.getElementById("routerType").value,
        username: document.getElementById("routerUser").value,
        password: document.getElementById("routerPass").value
    };
    
    try {
        const res = await fetch("/api/routers", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        const d = await res.json();
        if (res.ok) { closeAddModal(); fetchRouters(); }
        else { errBox.textContent = d.detail || d.error || "Failed connection test."; errBox.classList.remove("hidden"); }
    } catch (err) {
        errBox.textContent = "Network error. Connection failed.";
        errBox.classList.remove("hidden");
    } finally { btn.disabled = false; btn.textContent = "Test & Save"; }
});

async function deleteRouter(id) {
    if (confirm("Remove router?")) {
        const res = await fetch(`/api/routers/${id}`, { method: "DELETE" });
        if (res.ok) fetchRouters();
    }
}

function createRouterCard(r) {
    const div = document.createElement("div");
    div.className = "bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col space-y-3";
    div.id = `router-card-${r.id}`;
    div.innerHTML = `
        <div class="flex justify-between items-start">
            <div>
                <h3 class="text-sm font-bold text-white">${r.name}</h3>
                <p class="text-[10px] text-slate-400 font-mono mt-0.5">${r.host}:${r.port}</p>
            </div>
            <div class="flex items-center space-x-1.5">
                <span class="px-1.5 py-0.5 text-[9px] font-bold rounded uppercase ${r.connection_type === 'rest' ? 'bg-teal-950 text-teal-400 border border-teal-800' : 'bg-indigo-950 text-indigo-400 border border-indigo-800'}">${r.connection_type}</span>
                <button onclick="deleteRouter(${r.id})" class="text-slate-500 hover:text-red-400 text-xs">🗑️</button>
            </div>
        </div>
        <div class="grid grid-cols-3 gap-1.5 border-t border-b border-slate-800/80 py-2">
            <button onclick="fetchInfo(${r.id})" class="flex flex-col items-center p-1 bg-slate-950 hover:bg-slate-800 border border-slate-850 rounded text-[10px]">ℹ️ Info</button>
            <button onclick="fetchUpdates(${r.id})" class="flex flex-col items-center p-1 bg-slate-950 hover:bg-slate-800 border border-slate-850 rounded text-[10px]">🔄 Updates</button>
            <button onclick="fetchNtp(${r.id})" class="flex flex-col items-center p-1 bg-slate-950 hover:bg-slate-800 border border-slate-850 rounded text-[10px]">⏰ NTP</button>
        </div>
        <div id="panel-${r.id}" class="hidden bg-slate-950 rounded border border-slate-850 p-2 text-xs text-slate-300"></div>
    `;
    return div;
}

async function fetchDiag(rid, type, renderFn) {
    const p = document.getElementById(`panel-${rid}`);
    p.classList.remove("hidden");
    p.innerHTML = `<p class="text-slate-500 text-center animate-pulse py-1 text-[10px]">Fetching...</p>`;
    try {
        const res = await fetch(`/api/routers/${rid}/${type}`);
        const d = await res.json();
        if (!res.ok) return p.innerHTML = `<p class="text-red-400 text-[11px] font-semibold">Error: ${d.error || 'Failed'}</p><p class="text-[10px] text-slate-500 mt-0.5 leading-snug">${d.detail || ''}</p>`;
        p.innerHTML = renderFn(d);
    } catch (e) { p.innerHTML = `<p class="text-red-400 text-[10px]">Network error.</p>`; }
}

function fetchInfo(rid) {
    fetchDiag(rid, "info", d => {
        const cpu = parseInt(d.cpu_load) || 0;
        return `<div class="space-y-1.5">
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">Board:</span><span class="text-white font-medium">${d.board_name}</span></div>
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">OS:</span><span class="text-teal-400 font-medium">${d.version}</span></div>
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">Uptime:</span><span class="text-white font-medium">${d.uptime}</span></div>
            <div class="space-y-1">
                <div class="flex justify-between text-[9px] text-slate-400"><span>CPU:</span><span class="text-slate-200">${cpu}%</span></div>
                <div class="w-full bg-slate-800 h-1 rounded"><div class="bg-teal-400 h-1 rounded" style="width:${cpu}%"></div></div>
            </div>
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">RAM (F/T):</span><span class="text-slate-200">${fmtB(d.free_memory)} / ${fmtB(d.total_memory)}</span></div>
        </div>`;
    });
}

function fetchUpdates(rid) {
    fetchDiag(rid, "updates", d => {
        const ok = d.installed_version === d.latest_version && d.latest_version !== "Unknown";
        return `<div class="space-y-1.5">
            <div class="flex justify-between items-center"><span class="text-slate-400 text-[11px]">Status:</span><span class="px-1.5 py-0.5 text-[9px] font-bold rounded ${ok?'bg-green-950 text-green-400':'bg-amber-950 text-amber-400'}">${ok?"Up to date":"Update Available"}</span></div>
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">Installed:</span><span class="text-white">${d.installed_version}</span></div>
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">Latest:</span><span class="text-teal-400">${d.latest_version}</span></div>
            <div class="text-[9px] text-slate-500 italic mt-1 border-t border-slate-900 pt-1 text-center">${d.status || ""}</div>
        </div>`;
    });
}

function fetchNtp(rid) {
    fetchDiag(rid, "ntp", d => {
        const s = d.synced === "yes";
        return `<div class="space-y-1.5">
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">Enabled:</span><span class="text-white font-medium uppercase text-[10px]">${d.enabled}</span></div>
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">Synced:</span><span class="px-1.5 py-0.5 rounded text-[10px] ${s?'text-green-400 bg-green-950':'text-red-400 bg-red-950'}">${d.synced.toUpperCase()}</span></div>
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">Active Server:</span><span class="text-white">${d.active_server}</span></div>
            <div class="flex justify-between text-[11px]"><span class="text-slate-400">Offset:</span><span class="text-slate-300 font-mono">${d.offset}</span></div>
        </div>`;
    });
}



function refreshAllRouters() {
    document.querySelectorAll('[id^="router-card-"]').forEach(card => {
        fetchInfo(card.id.replace("router-card-", ""));
    });
}

function fmtB(str) {
    const b = parseInt(str);
    if (isNaN(b)) return str;
    if (b === 0) return '0 B';
    const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'], i = Math.floor(Math.log(b) / Math.log(k));
    return parseFloat((b / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

