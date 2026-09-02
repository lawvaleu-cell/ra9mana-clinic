// CliniQ — script principal

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
}

// ---------- Thème ----------
function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll(".theme-dot").forEach(el => {
        el.classList.toggle("active", el.dataset.theme === theme);
    });
}

function setTheme(theme) {
    applyTheme(theme);
    fetch("/parametres/theme", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme, csrf_token: getCsrfToken() }),
    }).catch(() => {});
}

// ---------- Sidebar mobile ----------
function toggleSidebar() {
    document.querySelector(".sidebar")?.classList.toggle("open");
}

// ---------- Flash auto-dismiss ----------
function initFlashes() {
    document.querySelectorAll(".flash").forEach(el => {
        setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 6000);
    });
}

// ---------- Modals ----------
function openModal(id) { document.getElementById(id)?.classList.add("open"); }
function closeModal(id) { document.getElementById(id)?.classList.remove("open"); }

// ---------- Recherche globale ----------
let searchTimeout = null;
function initGlobalSearch() {
    const input = document.getElementById("global-search-input");
    const dropdown = document.getElementById("global-search-dropdown");
    if (!input || !dropdown) return;

    input.addEventListener("input", () => {
        clearTimeout(searchTimeout);
        const q = input.value.trim();
        if (q.length < 2) { dropdown.classList.remove("open"); return; }
        searchTimeout = setTimeout(() => {
            fetch(`/recherche/api?q=${encodeURIComponent(q)}`)
                .then(r => r.json())
                .then(data => renderSearchResults(dropdown, data.results, q))
                .catch(() => {});
        }, 250);
    });

    document.addEventListener("click", (e) => {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove("open");
        }
    });
}

function renderSearchResults(dropdown, results, q) {
    const labels = {
        patients: "Patients", medicaments: "Médicaments", factures: "Factures",
        rendez_vous: "Rendez-vous", prescriptions: "Ordonnances"
    };
    const urls = {
        patients: id => `/patients/${id}`,
        medicaments: id => `/inventaire/${id}/modifier`,
        factures: id => `/facturation/${id}`,
        rendez_vous: () => `/rendez-vous/`,
        prescriptions: id => `/prescriptions/${id}`,
    };
    let html = "";
    let total = 0;
    for (const key in results) {
        const items = results[key];
        if (!items || !items.length) continue;
        total += items.length;
        html += `<div class="search-group-label">${labels[key] || key}</div>`;
        items.forEach(item => {
            let label = item.nom ? `${item.prenom || ""} ${item.nom}`.trim() : (item.numero_facture || "");
            html += `<a class="search-result-item" href="${urls[key](item.id)}"><span>${label}</span></a>`;
        });
    }
    dropdown.innerHTML = total ? html : `<div class="search-result-item text-muted">Aucun résultat pour "${q}"</div>`;
    dropdown.classList.add("open");
}

// ---------- Notification lue au clic ----------
function markNotificationRead(id) {
    fetch(`/notifications/${id}/lu`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
        body: JSON.stringify({}),
    }).catch(() => {});
}

// ---------- Impression avec choix du format papier ----------
let docPrintUrl = null, docPdfUrl = null, docTaille = "A4";
function openPaperSizeModal(printUrl, pdfUrl) {
    docPrintUrl = printUrl;
    docPdfUrl = pdfUrl;
    docTaille = "A4";
    document.querySelectorAll(".taille-btn").forEach(b => b.classList.toggle("active", b.dataset.taille === docTaille));
    openModal("modal-taille-papier");
}
function setTaillePapier(taille) {
    docTaille = taille;
    document.querySelectorAll(".taille-btn").forEach(b => b.classList.toggle("active", b.dataset.taille === taille));
}
function appendTaille(url) {
    return url + (url.includes("?") ? "&" : "?") + "taille=" + docTaille;
}
function confirmerImpression() {
    closeModal("modal-taille-papier");
    if (docPrintUrl) window.open(appendTaille(docPrintUrl), "_blank");
}
function confirmerTelechargement() {
    closeModal("modal-taille-papier");
    if (docPdfUrl) window.location.href = appendTaille(docPdfUrl);
}

document.addEventListener("DOMContentLoaded", () => {
    initFlashes();
    initGlobalSearch();
    document.querySelectorAll(".theme-dot").forEach(el => {
        el.addEventListener("click", () => setTheme(el.dataset.theme));
    });
    document.getElementById("sidebar-toggle-btn")?.addEventListener("click", toggleSidebar);
});
