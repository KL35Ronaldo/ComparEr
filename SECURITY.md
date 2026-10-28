# Security Policy

## Privacy Model

Followback is designed to be **privacy-preserving by default**.

### Browser-only mode (static / GitHub Pages)

- Your Instagram export ZIP is opened entirely in your browser using the [JSZip](https://stuk.github.io/jszip/) library.
- **No data is sent to any server**, remote API, analytics service, or third party.
- The ZIP file bytes are held in memory only for the duration of processing and are not stored anywhere.
- Usernames are not written to `localStorage`, `sessionStorage`, cookies, or any persistent browser storage.
- Closing or refreshing the tab releases all processed data.

### Python backend mode (optional)

- If you configure a backend URL, the ZIP file is uploaded to that server over HTTPS.
- The server reads the archive in memory, performs the comparison, and returns the result JSON.
- The server **must not** log usernames, write the archive to disk permanently, or persist account data.
- Temporary memory is cleared after each request.
- Review the backend code in `backend/app.py` and `backend/analyzer.py` before deploying to a third-party host.

---

## Reporting a Vulnerability

If you discover a security vulnerability in Followback, please report it responsibly:

1. **Do not open a public GitHub issue.**
2. Send a description of the vulnerability to the project maintainer directly (see the GitHub repository for contact information).
3. Include:
   - A description of the issue.
   - Steps to reproduce.
   - Your assessment of the potential impact.
   - Any suggested mitigations (optional but appreciated).
4. You will receive an acknowledgement within 72 hours where possible.
5. If the issue is confirmed, a fix will be prioritized and a public disclosure coordinated with you.

---

## Security Measures in This Project

| Concern | Mitigation |
|---------|-----------|
| ZIP bombs | Max 500 MB decompressed; max 10,000 entries enforced |
| Oversized uploads | 100 MB compressed limit (browser + backend) |
| Path traversal | Archive paths checked for `..` and absolute prefixes |
| HTML injection | Uploaded HTML parsed via DOMParser (browser) or stdlib HTMLParser (Python); never injected into the live DOM |
| Arbitrary URL execution | Instagram profile URLs validated against known host before use |
| JavaScript injection | `textContent` and safe DOM methods used exclusively; `eval` and `innerHTML` with untrusted data never used |
| CORS | Backend restricts cross-origin requests to the configured `ALLOWED_ORIGIN` |
| Debug mode | Flask debug mode is off by default in production |

---

## Disclaimer

This application has not been formally security-audited. Use it responsibly.
Instagram relationship data is personal. Do not share your export files with untrusted parties or services.
