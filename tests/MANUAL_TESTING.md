# Followback — Manual Testing Guide & Test Fixtures

This document describes how to test Followback using the provided synthetic fixtures and provides a step-by-step verification checklist for both browser-only (GitHub Pages) and Python backend modes.

---

## 1. Automated Test Suites

### A. Python Automated Unit & Integration Tests (62 Tests)
Run from the repository root:
```bash
# Using standard library unittest
python -m unittest tests.test_analyzer -v

# Or using pytest if installed
pytest tests/ -v
```
All 62 tests cover core comparison math, username normalization, URL extraction, JSON parsing, HTML parsing, multi-part follower aggregation, path traversal guards, ZIP bomb/entry limits, CSV escaping, and Flask API contract endpoints.

### B. Automated Browser Test Suite
Open [`tests/test_browser.html`](file:///e:/Documents/Python/Others/CompareEr/tests/test_browser.html) in any modern browser (Chrome, Safari, Firefox, Edge).
- Tests `JSZip` in-browser ZIP assembly and decompression.
- Tests `Parser.normalizeUsername` and `Parser.parseZip`.
- Tests `Comparator.compare` and `Comparator.toCSV`.
- Reports passed/failed counts with live visual badges.

---

## 2. Synthetic Test Fixtures

The [`tests/fixtures/`](file:///e:/Documents/Python/Others/CompareEr/tests/fixtures/) directory contains pre-generated synthetic test archives. To regenerate them at any time, run:
```bash
python tests/generate_fixtures.py
```

| Fixture File | Contents | Expected Result |
|--------------|----------|-----------------|
| `synthetic_standard_json.zip` | Followers: `alice`, `charlie`, `david`<br>Following: `alice`, `bob`, `charlie` | • **Don't Follow You Back:** `bob`<br>• **You Don't Follow Back:** `david`<br>• **Mutuals:** `alice`, `charlie` (excluded from non-mutual lists)<br>• Total Followers: 3, Following: 3 |
| `synthetic_standard_html.zip` | Same accounts as above, exported in Instagram HTML anchor format | Same output as JSON format |
| `synthetic_multi_followers.zip` | Followers split across `followers_1.json` (`alice`, `david`) and `followers_2.json` (`charlie`, `eve`).<br>Following: `alice`, `bob`, `charlie`, `frank` | • **Don't Follow You Back:** `bob`, `frank`<br>• **You Don't Follow Back:** `david`, `eve`<br>• **Mutuals:** 2 (`alice`, `charlie`)<br>• Total Followers: 4, Following: 4 |
| `synthetic_missing_followers.zip` | Contains `following.json` only | Displays friendly error: *"No followers file was found (e.g. followers_1.json)."* |

---

## 3. Manual Testing Checklist

Follow these steps to verify full functionality in the browser:

### Step 1: Open the Application
1. Double-click `index.html` or open `http://localhost:8080/` (if using a local server).
2. Check that the page loads with the purple-to-warm Instagram gradient atmosphere and Liquid Glass cards.
3. Check that the privacy badge displays: *"Your data stays yours"*.

### Step 2: Upload Standard JSON Archive
1. Drag and drop `tests/fixtures/synthetic_standard_json.zip` onto the upload zone (or click and select it).
2. Verify the loading state displays status messages:
   - *"Opening your archive…"*
   - *"Finding your follower lists…"*
   - *"Reading follower data…"*
   - *"Reading following data…"*
   - *"Comparing both lists…"*
3. Verify the summary statistics animate into view:
   - **Followers:** `3`
   - **Following:** `3`
   - **Mutuals:** `2`
   - **Don't Follow You Back:** `1`
   - **You Don't Follow Back:** `1`
4. Verify the two-column table displays:
   - **Left column:** `@bob`
   - **Right column:** `@david`
   - Shared accounts `alice` and `charlie` **must not** appear in either column.
5. Click on `@bob`: verify it opens `https://www.instagram.com/bob/` in a new tab with `rel="noopener noreferrer"`.

### Step 3: Test Real-Time Search / Filter
1. Type `bob` into the search box:
   - Left column shows `@bob`.
   - Right column displays *"No accounts match your search."*
2. Clear the search box: both columns restore their full account lists.

### Step 4: Test Copy & Download
1. Click the **Copy** button on the left column:
   - Toast displays: *"✓ Copied 1 username"*.
   - Paste into any text editor: verify `@bob` is pasted.
2. Click **Download CSV**:
   - Browser saves `followback-results.csv`.
   - Open the file: verify headers `"Don't Follow You Back","You Don't Follow Back"` with rows `bob,david`.

### Step 5: Test Multi-Part Follower Aggregation
1. Click **Analyze Another ZIP** to reset.
2. Upload `tests/fixtures/synthetic_multi_followers.zip`.
3. Verify total followers is `4` (combining `followers_1.json` and `followers_2.json`).
4. Verify non-mutual lists show `bob`, `frank` on the left and `david`, `eve` on the right.

### Step 6: Test HTML Format Support
1. Click **Analyze Another ZIP**.
2. Upload `tests/fixtures/synthetic_standard_html.zip`.
3. Verify results match the JSON format identically.

### Step 7: Test Error Handling
1. Click **Analyze Another ZIP**.
2. Upload `tests/fixtures/synthetic_missing_followers.zip`.
3. Verify an error banner appears explaining: *"No followers file was found (e.g. followers_1.json). Please ensure you selected the complete Instagram data export."*
4. Click **Try again**: verify the upload area resets to its ready state.
5. Try uploading a `.txt` file or non-ZIP file: verify it is rejected with a clear message.

### Step 8: Accessibility & Responsiveness
1. Press `Tab` to navigate to the upload button and press `Enter`: file dialog should open.
2. Open Browser DevTools responsive design mode:
   - Test at **375px** (mobile): columns stack cleanly into vertical cards, no horizontal scroll.
   - Test at **768px** (tablet) and **1200px** (desktop): two balanced columns render side-by-side.
3. In OS / browser settings, toggle **Reduced Motion**:
   - Verify numbers render immediately without count-up animation.
