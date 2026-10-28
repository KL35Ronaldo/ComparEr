# Followback

**Your circle, a little clearer.**

Followback is a private, browser-first Instagram Followers vs. Following analyzer.
Upload your Instagram data export ZIP and instantly see who doesn't follow you back —
and who you haven't followed back — without creating an account or sending your data anywhere.

---

## Features

- **100% private browser processing** — your ZIP never leaves your device in the default mode.
- Supports both **JSON** and **HTML** Instagram export formats.
- Handles **multiple numbered follower files** (`followers_1.json`, `followers_2.json`, …).
- Supports **nested archive paths** (Instagram can nest files inside sub-folders).
- Clean **two-column comparison table** with search and pagination.
- **Summary statistics**: followers, following, mutuals, and both non-mutual counts.
- **Export to CSV** and **copy to clipboard** for each category.
- Beautiful, responsive **Liquid Glass UI** inspired by Instagram's palette.
- Optional **Python/Flask backend** for server-side processing.
- No accounts, no tracking, no ads, no external CDN dependencies at runtime.

---

## How It Works

Let:
- **F** = accounts that follow you (your followers)
- **G** = accounts you follow (your following)

| Result | Formula | Meaning |
|--------|---------|---------|
| Don't Follow You Back | G − F | You follow them; they don't follow you |
| You Don't Follow Back | F − G | They follow you; you don't follow them |
| Mutuals | F ∩ G | You both follow each other |

All counts come from deduplicated, case-normalised sets. Usernames are lowercased before comparison so `Alice` and `alice` are treated as the same account.

---

## Screenshots

> _Screenshots to be added after first deployment._

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Semantic HTML5, CSS3 (Grid, Flexbox, custom properties), Vanilla JavaScript (ES2020+) |
| ZIP processing (browser) | [JSZip 3.10.1](https://stuk.github.io/jszip/) (vendored, MIT License) |
| Backend (optional) | Python 3.11+, Flask 3, flask-cors |
| Testing | Python `unittest` |
| CI | GitHub Actions |

---

## Project Structure

```
followback/
├── index.html              # Single-page application entry point
├── css/
│   └── styles.css          # All styles — design system, layout, animations
├── js/
│   ├── jszip.min.js        # Vendored ZIP library (MIT, locally bundled)
│   ├── parser.js           # ZIP reading, file discovery, JSON/HTML parsing
│   ├── comparator.js       # Set comparison logic and CSV export
│   └── app.js              # UI orchestration, upload, rendering, actions
├── assets/
│   ├── logo.svg            # App wordmark
│   ├── favicon.svg         # Browser tab icon
│   ├── icon-upload.svg     # Upload zone icon
│   └── icon-shield.svg     # Privacy indicator icon
├── backend/
│   ├── app.py              # Flask API server
│   ├── analyzer.py         # Core comparison logic (Python, no Flask dependency)
│   └── requirements.txt    # Python dependencies
├── tests/
│   ├── test_analyzer.py    # Automated Python unit tests (40+ test cases)
│   └── fixtures/           # Synthetic test data (JSON & HTML samples)
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI workflow
├── .gitignore
├── LICENSE                 # MIT License
├── README.md               # This file
└── SECURITY.md             # Security policy and privacy model
```

---

## Supported Instagram Export Formats

Instagram may export your data in two formats. Both are supported:

| Format | Follower file(s) | Following file |
|--------|-----------------|---------------|
| JSON   | `followers_1.json`, `followers_2.json`, … | `following.json` |
| HTML   | `followers_1.html`, `followers_2.html`, … | `following.html` |

Files may be nested inside sub-folders (e.g. `connections/followers_and_following/`). The application searches the entire archive automatically.

---

## How to Get Your Instagram Data Export

1. Open Instagram and tap your **Profile**. Tap the menu icon (☰).
2. Go to **Accounts Center** (under Settings & Privacy on some versions).
3. Select **Your information and permissions** → **Download your information**.
4. Choose your Instagram profile.
5. Tap **Select types of information** → select **Followers and following**.
6. Choose **JSON** (preferred) or **HTML** as the format; set date range to **All time**.
7. Tap **Create files**. Wait for Instagram's notification (minutes to a few hours).
8. Download the ZIP from the notification or from the same screen.
9. Upload the `.zip` file directly to Followback — **do not extract it first**.

> Instagram's interface wording may vary by app version. Visit the [Instagram Help Center](https://help.instagram.com/181231772500920) if labels differ.

---

## Running Locally (Frontend only — no backend needed)

The frontend works by simply opening `index.html` in a browser. Because it uses `file://` origins and `JSZip` is vendored locally, **no server is required**.

```powershell
# Windows PowerShell — just open the file
Start-Process "<your_directory>\CompareEr\index.html"
```

Or drag `index.html` into your browser.

If you prefer a local dev server (optional, for consistent origin):

```powershell
# Using Python's built-in server
cd "<your_directory>\CompareEr"
python -m http.server 8080
# Open http://localhost:8080 in your browser
```

---

## Running the Python Backend Locally

```powershell
# 1. Create and activate a virtual environment
cd "<your_directory>\CompareEr\backend"
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run in development mode
$env:FLASK_ENV = "development"
python app.py
# Server starts at http://localhost:5000
```

### Configuration

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `FLASK_ENV` | `production` | Set to `development` for debug mode and readable errors |
| `ALLOWED_ORIGIN` | `*` | CORS allowed origin. Set to your GitHub Pages URL in production |
| `MAX_UPLOAD_MB` | `100` | Maximum upload size in megabytes |
| `PORT` | `5000` | Port to listen on |

### Connecting the Frontend to the Backend

In `js/app.js`, set the `backendUrl` in the `CONFIG` object:

```javascript
const CONFIG = {
  backendUrl: "http://localhost:5000",  // or your production URL
  // ...
};
```

Leave `backendUrl` empty (`""`) to use browser-only mode (default and recommended).

---

## GitHub Pages Deployment

1. Push the repository to GitHub.
2. Go to **Settings** → **Pages** in your repository.
3. Set source to **Deploy from a branch**, select `main`, folder `/` (root).
4. Save. Your site will be available at `https://<your_github_username>.github.io/CompareEr/`.

> **Important:** GitHub Pages only serves static files. The Python backend does not run on GitHub Pages. Browser-only mode works perfectly with GitHub Pages.

No build step is needed. The frontend is pure HTML, CSS, and JavaScript.

---

## Python Backend Deployment

The backend can be deployed to any Python-compatible host.

### Render (free tier available)

1. Create a new **Web Service** on [Render](https://render.com).
2. Connect your GitHub repository.
3. Set:
   - **Root directory:** `backend`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`
4. Add environment variables:
   - `ALLOWED_ORIGIN`: your GitHub Pages URL
   - `FLASK_ENV`: `production`
5. Deploy. Copy the service URL into `js/app.js` → `CONFIG.backendUrl`.

### Railway / Fly.io / Heroku

Similar pattern: set the working directory to `backend/`, install from `requirements.txt`, and run `gunicorn app:app`.

Add `gunicorn` to `requirements.txt` for production:

```
flask>=3.0.0
flask-cors>=4.0.0
gunicorn>=21.0.0
```

---

## Privacy and Data Handling

| Mode | What happens to your data |
|------|--------------------------|
| **Browser-only (default)** | The ZIP is read in your browser's memory. Nothing is sent to any server. Data is gone when you close or refresh the tab. |
| **Python backend (optional)** | The ZIP is uploaded to your configured server over HTTPS, processed in memory, and the result JSON is returned. The server does not write the archive to disk or log account names. |

Followback never:
- Requests your Instagram password or credentials.
- Logs into Instagram.
- Scrapes Instagram.
- Uploads your data to analytics or telemetry services.
- Stores account names in logs, databases, or browser storage.

---

## Known Limitations

- Results reflect a **snapshot** of your export data. Accounts may have changed usernames, gone private, or been deactivated since the export was created.
- Instagram does not mark *when* someone unfollowed you. This tool cannot tell you who recently unfollowed you — only who does not follow you at the time of the export.
- If Instagram significantly changes its export format, parsing may need to be updated.
- The HTML export format contains less metadata than JSON. JSON is recommended for the most reliable results.
- Very large follower lists (>50,000 accounts) may take a few seconds to process in the browser on slower devices.

---

## Troubleshooting

**"No followers file was found"**
Ensure you uploaded the complete Instagram export ZIP without extracting it first. The ZIP must contain `followers_1.json` (or `.html`) at some path inside the archive.

**"The file is not a valid ZIP archive"**
Make sure you're uploading the `.zip` file downloaded from Instagram, not an extracted folder or a different type of file.

**"No recognizable account data found"**
Your export may use a format not yet supported. Try switching between JSON and HTML format in the Instagram export settings and re-requesting the export.

**Results seem wrong or empty**
Check that your export includes the "Followers and following" section. Some export types only include posts, stories, or messages.

---

## Contributing

Contributions, bug reports, and suggestions are welcome.

- Open an issue to discuss a bug or feature before submitting a pull request.
- Keep pull requests focused on a single concern.
- Run the test suite before submitting: `python -m unittest discover -s tests -v`
- Match the existing code style: clear names, focused functions, no unnecessary abstractions.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

Third-party components:
- **JSZip 3.10.1** (vendored in `js/jszip.min.js`) — MIT License — Copyright (c) 2009-2016 Stuart Knightley et al.
