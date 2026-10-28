/**
 * parser.js — ZIP reading, file discovery, JSON/HTML parsing
 * Works in the browser using the JSZip library (vendored).
 */

"use strict";

const Parser = (() => {

  // ── Constants ──────────────────────────────────────────────
  const MAX_ZIP_BYTES = 100 * 1024 * 1024; // 100 MB raw ZIP
  const MAX_UNCOMPRESSED = 500 * 1024 * 1024; // 500 MB uncompressed guard
  const MAX_ENTRIES = 10_000;
  const INSTAGRAM_DOMAIN_RE = /^https?:\/\/(www\.)?instagram\.com\//i;

  // Pattern: followers_1.json, followers_2.json … but NOT following_hashtags etc.
  const FOLLOWERS_FILE_RE = /(?:^|[\\/])followers(?:_\d+)?\.(?:json|html)$/i;
  // following.json / following.html — must end exactly, no extras
  const FOLLOWING_FILE_RE = /(?:^|[\\/])following\.(?:json|html)$/i;

  // ── Normalize username ─────────────────────────────────────
  function normalizeUsername(raw) {
    if (typeof raw !== "string") return null;
    const u = raw.trim().toLowerCase().replace(/^@/, "");
    // Basic Instagram username validation (1–30 chars, alphanumeric+._)
    if (!/^[\w.]{1,30}$/.test(u)) return null;
    return u;
  }

  // ── Validate Instagram href and extract username ────────────
  function usernameFromHref(href) {
    if (typeof href !== "string") return null;
    try {
      const url = new URL(href);
      if (!/^https?:$/.test(url.protocol)) return null;
      if (!url.hostname.endsWith("instagram.com")) return null;
      const parts = url.pathname.replace(/^\//, "").replace(/\/$/, "").split("/");
      if (parts.length !== 1) return null;
      return normalizeUsername(parts[0]);
    } catch {
      return null;
    }
  }

  // ── Extract usernames from Instagram JSON structure ─────────
  function extractFromJSON(data) {
    const results = new Set();

    function processEntry(entry) {
      if (!entry || typeof entry !== "object") return;

      // Format: { string_list_data: [{ value: "username", href: "...", timestamp: N }] }
      if (Array.isArray(entry.string_list_data)) {
        for (const item of entry.string_list_data) {
          if (item && typeof item === "object") {
            const u = normalizeUsername(item.value) || usernameFromHref(item.href);
            if (u) results.add(u);
          }
        }
      }

      // Format: { value: "username" }
      if (typeof entry.value === "string") {
        const u = normalizeUsername(entry.value);
        if (u) results.add(u);
      }

      // Format: { href: "https://instagram.com/username" }
      if (typeof entry.href === "string") {
        const u = usernameFromHref(entry.href);
        if (u) results.add(u);
      }
    }

    // Top-level array (followers format)
    if (Array.isArray(data)) {
      for (const item of data) processEntry(item);
      return results;
    }

    // Top-level object (following format often uses { relationships_following: [...] })
    if (data && typeof data === "object") {
      for (const key of Object.keys(data)) {
        const val = data[key];
        if (Array.isArray(val)) {
          for (const item of val) processEntry(item);
        } else {
          processEntry(val);
        }
      }
    }

    return results;
  }

  // ── Extract usernames from Instagram exported HTML ──────────
  function extractFromHTML(html) {
    const results = new Set();
    if (typeof html !== "string" || html.length === 0) return results;

    // Use DOMParser to safely parse — never inject into the live document
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    // Instagram HTML exports: profile links are <a href="https://www.instagram.com/username">username</a>
    const anchors = doc.querySelectorAll("a");
    for (const a of anchors) {
      const hrefAttr = a.getAttribute("href");

      if (hrefAttr !== null) {
        // href attribute present — only use if it's a valid Instagram URL.
        // Do NOT fall back to anchor text when a non-Instagram href is present.
        const fromHref = usernameFromHref(hrefAttr);
        if (fromHref) results.add(fromHref);
      } else {
        // No href attribute — try anchor text as fallback
        const text = (a.textContent || "").trim();
        const u = normalizeUsername(text);
        if (u) results.add(u);
      }
    }

    // Some exports embed usernames as plain text list items (no anchors)
    if (results.size === 0) {
      const items = doc.querySelectorAll("li, td, .body-text");
      for (const el of items) {
        const text = (el.textContent || "").trim();
        const u = normalizeUsername(text);
        if (u) results.add(u);
      }
    }

    return results;
  }

  // ── Parse a file (JSON or HTML) from a string ───────────────
  function parseFileContent(filename, content) {
    const isJSON = /\.json$/i.test(filename);
    const isHTML = /\.html?$/i.test(filename);

    if (!isJSON && !isHTML) {
      throw new Error(`Unsupported file format: ${filename}`);
    }

    if (isJSON) {
      let data;
      try { data = JSON.parse(content); }
      catch {
        throw new Error(`The file "${filename}" contains invalid JSON. It may be corrupted.`);
      }
      const users = extractFromJSON(data);
      if (users.size === 0) {
        throw new Error(`No recognizable account data found in "${filename}". The export format may be unsupported.`);
      }
      return users;
    }

    // HTML
    const users = extractFromHTML(content);
    if (users.size === 0) {
      throw new Error(`No recognizable account links found in "${filename}". The HTML format may be unsupported.`);
    }
    return users;
  }

  // ── Discover relevant files inside a JSZip instance ─────────
  async function discoverFiles(zip) {
    const followerFiles = [];
    const followingFiles = [];
    let entryCount = 0;
    let totalUncompressed = 0;

    for (const [path, entry] of Object.entries(zip.files)) {
      if (entry.dir) continue;

      entryCount++;
      if (entryCount > MAX_ENTRIES) {
        throw new Error("This archive contains too many entries. It may not be a valid Instagram export.");
      }

      // Guard against path traversal (JSZip already normalises, but double-check)
      if (path.includes("..") || path.startsWith("/")) {
        throw new Error(`Suspicious archive path detected: "${path}". Processing stopped.`);
      }

      // Track uncompressed size
      const meta = entry._data;
      if (meta && meta.uncompressedSize) {
        totalUncompressed += meta.uncompressedSize;
        if (totalUncompressed > MAX_UNCOMPRESSED) {
          throw new Error("The archive would expand to an unsafe size. It may be a ZIP bomb or an incorrect file.");
        }
      }

      const lower = path.toLowerCase();
      const name = lower.split("/").pop();

      if (FOLLOWERS_FILE_RE.test(name)) {
        followerFiles.push(path);
      } else if (FOLLOWING_FILE_RE.test(name)) {
        followingFiles.push(path);
      }
    }

    if (followerFiles.length === 0 && followingFiles.length === 0) {
      throw new Error(
        "No followers or following files were found in this archive. " +
        "Make sure you uploaded an Instagram data export ZIP (not extracted)."
      );
    }

    if (followerFiles.length === 0) {
      throw new Error(
        "No followers file was found (e.g. followers_1.json). " +
        "Please ensure you selected the complete Instagram data export."
      );
    }

    if (followingFiles.length === 0) {
      throw new Error(
        "No following file was found (e.g. following.json). " +
        "Please ensure you selected the complete Instagram data export."
      );
    }

    return { followerFiles, followingFiles };
  }

  // ── Read and parse a single zip entry ───────────────────────
  async function readEntry(zip, path) {
    const entry = zip.files[path];
    if (!entry) throw new Error(`Expected file not found in archive: "${path}"`);

    let content;
    try { content = await entry.async("string"); }
    catch { throw new Error(`Failed to read "${path}" from the archive. It may be corrupted.`); }

    const filename = path.split("/").pop();
    return parseFileContent(filename, content);
  }

  // ── Main parse entrypoint ────────────────────────────────────
  async function parseZip(file, onStatus) {
    if (!file) throw new Error("No file provided.");
    if (file.size > MAX_ZIP_BYTES) {
      throw new Error(`The file is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum supported size is 100 MB.`);
    }

    onStatus("Opening your archive…");

    // Read raw bytes
    const buffer = await file.arrayBuffer();

    // Validate ZIP signature (PK magic bytes: 0x50 0x4B 0x03 0x04)
    const magic = new Uint8Array(buffer, 0, 4);
    if (magic[0] !== 0x50 || magic[1] !== 0x4B || magic[2] !== 0x03 || magic[3] !== 0x04) {
      throw new Error("The selected file is not a valid ZIP archive. Please upload the original Instagram export ZIP.");
    }

    // Load with JSZip
    let zip;
    try { zip = await JSZip.loadAsync(buffer); }
    catch { throw new Error("Failed to open the ZIP archive. It may be corrupted or password-protected."); }

    onStatus("Finding your follower lists…");
    const { followerFiles, followingFiles } = await discoverFiles(zip);

    onStatus("Reading follower data…");
    let followersSet = new Set();
    for (const path of followerFiles) {
      const partial = await readEntry(zip, path);
      for (const u of partial) followersSet.add(u);
    }

    onStatus("Reading following data…");
    const followingSet = await readEntry(zip, followingFiles[0]);

    onStatus("Comparing both lists…");
    // Allow a tick for UI to update
    await new Promise(r => setTimeout(r, 16));

    return { followersSet, followingSet };
  }

  return { parseZip, normalizeUsername };

})();
