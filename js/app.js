/**
 * app.js — UI orchestration, upload handling, rendering, actions
 * Depends on: parser.js, comparator.js (loaded before this file)
 */

"use strict";

// ── Configuration ─────────────────────────────────────────────
const CONFIG = {
  // Set to your backend URL to enable Python API mode, e.g.:
  //   backendUrl: "https://your-app.onrender.com"
  // Leave empty ("") to use browser-only mode (default, recommended).
  backendUrl: "",

  // Accounts per page in results columns (0 = no pagination)
  pageSize: 100,

  githubUrl: "https://github.com/KL35Ronaldo/CompareEr",
};

// ── Mode detection ────────────────────────────────────────────
const USE_BACKEND = Boolean(CONFIG.backendUrl && CONFIG.backendUrl.trim());

// ── State ─────────────────────────────────────────────────────
let state = {
  processing: false,
  results: null,
  pageLeft: 0,
  pageRight: 0,
  searchQuery: "",
};

// ── DOM refs ──────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const els = {
  fileInput: $("file-input"),
  uploadZone: $("upload-zone"),
  processingSection: $("processing-section"),
  processingMsg: $("processing-msg"),
  errorSection: $("error-section"),
  errorHeading: $("error-heading"),
  errorBody: $("error-body"),
  errorReset: $("error-reset"),
  resultsSection: $("results-section"),
  statFollowers: $("stat-followers"),
  statFollowing: $("stat-following"),
  statMutuals: $("stat-mutuals"),
  statNotBack: $("stat-not-back"),
  statNotFollowed: $("stat-not-followed"),
  colLeftTitle: $("col-left-title"),
  colLeftCount: $("col-left-count"),
  colRightTitle: $("col-right-title"),
  colRightCount: $("col-right-count"),
  listLeft: $("list-left"),
  listRight: $("list-right"),
  noResultsLeft: $("no-results-left"),
  noResultsRight: $("no-results-right"),
  paginLeft: $("pagin-left"),
  paginRight: $("pagin-right"),
  searchInput: $("search-input"),
  btnDownload: $("btn-download"),
  btnReset: $("btn-reset"),
  btnCopyLeft: $("btn-copy-left"),
  btnCopyRight: $("btn-copy-right"),
  srLive: $("sr-live"),
  toast: $("toast"),
  instrToggle: $("instructions-toggle"),
  instrBody: $("instructions-body"),
};

// ── Announce to screen readers ────────────────────────────────
function announce(msg) {
  if (!els.srLive) return;
  els.srLive.textContent = "";
  requestAnimationFrame(() => { els.srLive.textContent = msg; });
}

// ── Toast notification ─────────────────────────────────────────
let toastTimer = null;
function showToast(msg, duration = 2800) {
  const t = els.toast;
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), duration);
}

// ── Instructions accordion ─────────────────────────────────────
function initInstructions() {
  const toggle = els.instrToggle;
  const body = els.instrBody;
  if (!toggle || !body) return;

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
  });
}

// ── Upload zone ───────────────────────────────────────────────
function initUpload() {
  const zone = els.uploadZone;
  const input = els.fileInput;

  // Click / keyboard: open file picker
  zone.addEventListener("click", () => !state.processing && input.click());
  zone.addEventListener("keydown", e => {
    if ((e.key === "Enter" || e.key === " ") && !state.processing) {
      e.preventDefault();
      input.click();
    }
  });

  // File selected via picker
  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (file) handleFile(file);
    // Reset so same file can be re-selected
    input.value = "";
  });

  // Drag-and-drop
  zone.addEventListener("dragenter", e => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", e => {
    if (!zone.contains(e.relatedTarget)) zone.classList.remove("drag-over");
  });
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    const file = e.dataTransfer?.files?.[0];
    if (file) handleFile(file);
  });

  // Prevent dropping on document
  document.addEventListener("dragover", e => e.preventDefault());
  document.addEventListener("drop", e => e.preventDefault());
}

// ── File handling orchestration ───────────────────────────────
async function handleFile(file) {
  if (state.processing) return;
  if (!file.name.toLowerCase().endsWith(".zip") && file.type !== "application/zip") {
    showError("Invalid file type", "Please select a .zip file. Instagram exports are delivered as ZIP archives.");
    return;
  }

  state.processing = true;
  hideError();
  hideResults();
  showProcessing();
  announce("Processing your archive…");

  try {
    let results;

    if (USE_BACKEND) {
      results = await analyzeWithBackend(file);
    } else {
      results = await analyzeInBrowser(file);
    }

    state.results = results;
    state.pageLeft = 0;
    state.pageRight = 0;
    state.searchQuery = "";

    renderResults(results);
    announce(`Analysis complete. ${results.notFollowingBack.length} accounts don't follow you back. ${results.notFollowedBack.length} accounts you don't follow back.`);

  } catch (err) {
    const msg = (err && err.message) ? err.message : "An unexpected error occurred.";
    showError("Processing failed", msg);
    announce("Processing failed: " + msg);
    console.error("[Followback]", err);
  } finally {
    state.processing = false;
    hideProcessing();
  }
}

// ── Browser-only analysis ─────────────────────────────────────
async function analyzeInBrowser(file) {
  if (typeof JSZip === "undefined") {
    throw new Error("The ZIP processing library is not loaded. Please refresh the page.");
  }

  const { followersSet, followingSet } = await Parser.parseZip(file, setProcessingMsg);

  setProcessingMsg("Putting your results together…");
  await new Promise(r => setTimeout(r, 32)); // yield

  return Comparator.compare(followersSet, followingSet);
}

// ── Backend API analysis ──────────────────────────────────────
async function analyzeWithBackend(file) {
  setProcessingMsg("Sending archive to server…");

  const formData = new FormData();
  formData.append("file", file);

  const url = CONFIG.backendUrl.replace(/\/$/, "") + "/api/analyze";

  let response;
  try {
    response = await fetch(url, { method: "POST", body: formData });
  } catch (err) {
    throw new Error("Could not reach the analysis server. Check your connection and try again.");
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const msg = data?.error || `Server error (${response.status}).`;
    throw new Error(msg);
  }

  if (!data || !data.success) {
    throw new Error(data?.error || "The server returned an unexpected response.");
  }

  return {
    followers: data.statistics.followers,
    following: data.statistics.following,
    mutuals: data.statistics.mutuals,
    notFollowingBack: data.not_following_back,
    notFollowedBack: data.not_followed_back,
  };
}

// ── UI state helpers ──────────────────────────────────────────
function setProcessingMsg(msg) {
  if (els.processingMsg) els.processingMsg.textContent = msg;
}

function showProcessing() {
  els.uploadZone.classList.add("processing");
  els.processingSection.classList.add("visible");
}

function hideProcessing() {
  els.uploadZone.classList.remove("processing");
  els.processingSection.classList.remove("visible");
}

function showError(heading, body) {
  els.errorHeading.textContent = heading;
  els.errorBody.textContent = body;
  els.errorSection.classList.add("visible");
  els.uploadZone.classList.add("error-state");
}

function hideError() {
  els.errorSection.classList.remove("visible");
  els.uploadZone.classList.remove("error-state", "file-selected");
}

function hideResults() {
  els.resultsSection.classList.remove("visible");
}

// ── Render results ────────────────────────────────────────────
function renderResults(results) {
  // Stats
  animateNumber(els.statFollowers, results.followers);
  animateNumber(els.statFollowing, results.following);
  animateNumber(els.statMutuals, results.mutuals);
  animateNumber(els.statNotBack, results.notFollowingBack.length);
  animateNumber(els.statNotFollowed, results.notFollowedBack.length);

  // Column headers
  const leftCount = results.notFollowingBack.length;
  const rightCount = results.notFollowedBack.length;
  els.colLeftCount.textContent = `· ${leftCount.toLocaleString()}`;
  els.colRightCount.textContent = `· ${rightCount.toLocaleString()}`;

  // Render lists
  renderColumn(els.listLeft, results.notFollowingBack, state.pageLeft);
  renderColumn(els.listRight, results.notFollowedBack, state.pageRight);
  renderPagination(els.paginLeft, results.notFollowingBack, "left");
  renderPagination(els.paginRight, results.notFollowedBack, "right");

  els.uploadZone.classList.add("file-selected");
  els.resultsSection.classList.add("visible");
  els.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Number animation ──────────────────────────────────────────
function animateNumber(el, target) {
  if (!el) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) { el.textContent = target.toLocaleString(); return; }

  const duration = 600;
  const start = performance.now();
  const from = 0;

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    el.textContent = Math.round(from + (target - from) * eased).toLocaleString();
    if (progress < 1) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

// ── Render a paginated column list ────────────────────────────
function renderColumn(listEl, usernames, page) {
  listEl.innerHTML = "";

  const query = state.searchQuery.toLowerCase().trim();
  const filtered = query
    ? usernames.filter(u => u.includes(query))
    : usernames;

  const ps = CONFIG.pageSize || 0;
  const show = (ps > 0) ? filtered.slice(page * ps, (page + 1) * ps) : filtered;

  if (filtered.length === 0) {
    const li = document.createElement("li");
    li.className = "account-empty";
    li.textContent = usernames.length === 0
      ? "None — everyone's accounted for! 🎉"
      : "No accounts match your search.";
    listEl.appendChild(li);
    return;
  }

  const frag = document.createDocumentFragment();
  for (const username of show) {
    const li = document.createElement("li");
    li.className = "account-item";

    const a = document.createElement("a");
    a.href = `https://www.instagram.com/${encodeURIComponent(username)}/`;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = username; // safe: no HTML injection

    li.appendChild(a);
    frag.appendChild(li);
  }

  listEl.appendChild(frag);
}

// ── Pagination controls ───────────────────────────────────────
function renderPagination(paginEl, usernames, side) {
  paginEl.innerHTML = "";
  const ps = CONFIG.pageSize || 0;
  if (ps === 0) return;

  const query = state.searchQuery.toLowerCase().trim();
  const filtered = query ? usernames.filter(u => u.includes(query)) : usernames;
  const pages = Math.ceil(filtered.length / ps);
  if (pages <= 1) return;

  const currentPage = side === "left" ? state.pageLeft : state.pageRight;

  for (let i = 0; i < pages; i++) {
    const btn = document.createElement("button");
    btn.className = "page-btn" + (i === currentPage ? " active" : "");
    btn.textContent = i + 1;
    btn.setAttribute("aria-label", `Page ${i + 1}`);
    btn.addEventListener("click", () => {
      if (side === "left") {
        state.pageLeft = i;
        renderColumn(els.listLeft, state.results.notFollowingBack, i);
      } else {
        state.pageRight = i;
        renderColumn(els.listRight, state.results.notFollowedBack, i);
      }
      renderPagination(paginEl, usernames, side);
    });
    paginEl.appendChild(btn);
  }
}

// ── Search ────────────────────────────────────────────────────
function initSearch() {
  if (!els.searchInput) return;
  els.searchInput.addEventListener("input", () => {
    if (!state.results) return;
    state.searchQuery = els.searchInput.value;
    state.pageLeft = 0;
    state.pageRight = 0;
    renderColumn(els.listLeft, state.results.notFollowingBack, 0);
    renderColumn(els.listRight, state.results.notFollowedBack, 0);
    renderPagination(els.paginLeft, state.results.notFollowingBack, "left");
    renderPagination(els.paginRight, state.results.notFollowedBack, "right");
  });
}

// ── Actions ───────────────────────────────────────────────────
function initActions() {
  // Download CSV
  els.btnDownload?.addEventListener("click", downloadCSV);

  // Reset
  els.btnReset?.addEventListener("click", resetApp);
  els.errorReset?.addEventListener("click", resetApp);

  // Copy columns
  els.btnCopyLeft?.addEventListener("click", () => copyUsernames("left"));
  els.btnCopyRight?.addEventListener("click", () => copyUsernames("right"));
}

function downloadCSV() {
  if (!state.results) return;
  const csv = Comparator.toCSV(state.results);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "followback-results.csv";
  a.click();
  URL.revokeObjectURL(url);
  showToast("✓ CSV downloaded");
  announce("Results downloaded as CSV.");
}

function copyUsernames(side) {
  if (!state.results) return;
  const list = side === "left"
    ? state.results.notFollowingBack
    : state.results.notFollowedBack;
  const text = list.map(u => "@" + u).join("\n");

  navigator.clipboard.writeText(text).then(() => {
    const label = side === "left" ? "Don't Follow You Back" : "You Don't Follow Back";
    showToast(`✓ Copied ${list.length} username${list.length !== 1 ? "s" : ""}`);
    announce(`${list.length} usernames from "${label}" copied to clipboard.`);
  }).catch(() => {
    showToast("Could not access clipboard. Try selecting and copying manually.");
  });
}

function resetApp() {
  state = {
    processing: false,
    results: null,
    pageLeft: 0,
    pageRight: 0,
    searchQuery: "",
  };

  hideError();
  hideResults();
  hideProcessing();

  els.uploadZone.classList.remove("file-selected", "processing", "error-state", "drag-over");
  els.listLeft.innerHTML = "";
  els.listRight.innerHTML = "";
  if (els.searchInput) els.searchInput.value = "";
  if (els.paginLeft) els.paginLeft.innerHTML = "";
  if (els.paginRight) els.paginRight.innerHTML = "";

  window.scrollTo({ top: 0, behavior: "smooth" });
  announce("Reset. Ready to analyze a new archive.");
}

// ── Mode badge ────────────────────────────────────────────────
function renderModeBadge() {
  const badge = document.getElementById("mode-badge");
  if (!badge) return;
  if (USE_BACKEND) {
    badge.textContent = "Server mode";
    badge.title = `Analyzing via backend: ${CONFIG.backendUrl}`;
  } else {
    badge.textContent = "Local mode — data stays on your device";
  }
}

// ── Init ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initUpload();
  initInstructions();
  initSearch();
  initActions();
  renderModeBadge();
});
