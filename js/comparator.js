/**
 * comparator.js — Set comparison and statistics
 * Pure functions; no DOM or network access.
 */

"use strict";

const Comparator = (() => {

  /**
   * Compare followers and following sets.
   *
   * Let F = followers (accounts that follow the user)
   *     G = following (accounts the user follows)
   *
   * notFollowingBack = G − F  (user follows, they don't follow back)
   * notFollowedBack  = F − G  (they follow user, user doesn't follow them)
   * mutuals          = F ∩ G
   */
  function compare(followersSet, followingSet) {
    if (!(followersSet instanceof Set) || !(followingSet instanceof Set)) {
      throw new TypeError("Both arguments must be Sets.");
    }

    const notFollowingBack = []; // G − F
    const notFollowedBack  = []; // F − G
    const mutuals          = []; // F ∩ G

    for (const username of followingSet) {
      if (followersSet.has(username)) {
        mutuals.push(username);
      } else {
        notFollowingBack.push(username);
      }
    }

    for (const username of followersSet) {
      if (!followingSet.has(username)) {
        notFollowedBack.push(username);
      }
    }

    // Sort alphabetically for stable display order
    notFollowingBack.sort((a, b) => a.localeCompare(b));
    notFollowedBack.sort((a, b) => a.localeCompare(b));
    mutuals.sort((a, b) => a.localeCompare(b));

    return {
      followers:       followersSet.size,
      following:       followingSet.size,
      mutuals:         mutuals.length,
      notFollowingBack,     // G − F: they don't follow you back
      notFollowedBack,      // F − G: you don't follow them back
    };
  }

  /**
   * Generate CSV content from comparison results.
   * Properly escapes fields containing commas, quotes, or newlines.
   */
  function toCSV(results) {
    const esc = (val) => {
      const s = String(val);
      if (/[,"\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
      return s;
    };

    const rows = [["Don't Follow You Back", "You Don't Follow Back"]];
    const len = Math.max(results.notFollowingBack.length, results.notFollowedBack.length);

    for (let i = 0; i < len; i++) {
      rows.push([
        results.notFollowingBack[i] ?? "",
        results.notFollowedBack[i]  ?? "",
      ]);
    }

    return rows.map(row => row.map(esc).join(",")).join("\r\n");
  }

  return { compare, toCSV };

})();
