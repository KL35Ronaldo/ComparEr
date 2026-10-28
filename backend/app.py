"""
app.py — Flask backend for Followback.

Endpoints:
  GET  /api/health   — liveness check
  POST /api/analyze  — upload ZIP, receive comparison JSON

Environment variables:
  FLASK_ENV           — "production" or "development" (default: production)
  ALLOWED_ORIGIN      — CORS allowed origin (default: *)
  MAX_UPLOAD_MB       — override max upload size in MB (default: 100)
  PORT                — port to listen on (default: 5000)
"""

from __future__ import annotations

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from analyzer import AnalyzerError, analyze_zip_bytes

# ── App setup ─────────────────────────────────────────────────
app = Flask(__name__)

# CORS — restrict to configured origin in production
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGIN}})

# Upload size limit
MAX_UPLOAD_MB  = int(os.environ.get("MAX_UPLOAD_MB", "100"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# Never expose debug info in production
app.config["PROPAGATE_EXCEPTIONS"] = False


# ── Error handlers ────────────────────────────────────────────
@app.errorhandler(413)
def request_entity_too_large(_):
    return jsonify(success=False, error=f"File too large. Maximum size is {MAX_UPLOAD_MB} MB."), 413


@app.errorhandler(400)
def bad_request(e):
    return jsonify(success=False, error=str(e)), 400


@app.errorhandler(500)
def internal_error(_):
    return jsonify(success=False, error="An unexpected server error occurred. Please try again."), 500


# ── Health check ──────────────────────────────────────────────
@app.get("/api/health")
def health():
    return jsonify(status="ok", mode="backend"), 200


# ── Analysis endpoint ─────────────────────────────────────────
@app.post("/api/analyze")
def analyze():
    if "file" not in request.files:
        return jsonify(success=False, error="No file was included in the request."), 400

    uploaded = request.files["file"]

    if not uploaded.filename:
        return jsonify(success=False, error="No filename provided."), 400

    if not uploaded.filename.lower().endswith(".zip"):
        return jsonify(success=False, error="Only .zip files are accepted."), 400

    # Read bytes — limit is enforced by MAX_CONTENT_LENGTH above
    raw_bytes = uploaded.read()

    try:
        result = analyze_zip_bytes(raw_bytes)
    except AnalyzerError as e:
        return jsonify(success=False, error=str(e)), e.status
    except Exception:
        # Log server-side (not to client) in production
        app.logger.exception("Unexpected error during analysis")
        return jsonify(success=False, error="An unexpected error occurred."), 500
    finally:
        raw_bytes = b""  # release reference

    return jsonify(
        success=True,
        statistics={
            "followers":          result.followers,
            "following":          result.following,
            "mutuals":            result.mutuals,
            "not_following_back": len(result.not_following_back),
            "not_followed_back":  len(result.not_followed_back),
        },
        not_following_back=result.not_following_back,
        not_followed_back=result.not_followed_back,
    ), 200


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
