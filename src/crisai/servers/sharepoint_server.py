from __future__ import annotations

import logging
import csv
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import chardet
import requests
from docx import Document as DocxDocument
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from msal import PublicClientApplication, SerializableTokenCache
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader

load_dotenv()

mcp = FastMCP("crisai-sharepoint")

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
ROOT.mkdir(parents=True, exist_ok=True)

LOG_FILE = ROOT / "sharepoint_mcp.log"
CACHE_DIR = ROOT / ".auth"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_CACHE_PATH = Path(os.getenv("MS_TOKEN_CACHE_PATH", CACHE_DIR / "msal_token_cache.json"))

TENANT_ID = os.getenv("MS_TENANT_ID", "")
CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else ""
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

DEFAULT_SCOPES = [
    "User.Read",
    "Sites.Read.All",
    "Files.Read.All",
]

SUPPORTED_TEXT_SUFFIXES = {".txt", ".md", ".json", ".yaml", ".yml", ".py", ".log", ".csv"}
SUPPORTED_DOC_SUFFIXES = {".docx", ".pdf", ".pptx", ".xlsx"}

TOKEN_INFO_PATH = Path(os.getenv("MS_TOKEN_INFO_PATH", CACHE_DIR / "msal_token_info.json"))

def _acquire_token_silent_only(scopes: list[str] | None = None) -> dict[str, Any] | None:
    _require_env()
    scopes = scopes or DEFAULT_SCOPES

    cache = _load_token_cache()
    app = _build_app(cache)

    accounts = app.get_accounts()
    if not accounts:
        return None

    result = app.acquire_token_silent(scopes=scopes, account=accounts[0])
    _save_token_cache(cache)
    return result

def _write_token_info(info: dict[str, Any]) -> None:
    TOKEN_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_INFO_PATH.write_text(json.dumps(info, indent=2), encoding="utf-8")


def _read_token_info() -> dict[str, Any]:
    if TOKEN_INFO_PATH.exists():
        return json.loads(TOKEN_INFO_PATH.read_text(encoding="utf-8"))
    return {}



def _configure_mcp_logging() -> None:
    """Keep MCP framework INFO logs out of the interactive CLI.

    Warnings and errors are still written to this server log file.
    """
    logger_names = [
        "mcp",
        "mcp.server",
        "mcp.server.fastmcp",
        "mcp.server.lowlevel",
        "mcp.server.lowlevel.server",
    ]

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)

    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.addHandler(file_handler)
        logger.propagate = False

def log_event(message: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {message}\n")


def _require_env() -> None:
    missing = []
    if not TENANT_ID:
        missing.append("MS_TENANT_ID")
    if not CLIENT_ID:
        missing.append("MS_CLIENT_ID")
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def _load_token_cache() -> SerializableTokenCache:
    cache = SerializableTokenCache()
    if TOKEN_CACHE_PATH.exists():
        cache.deserialize(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
    return cache


def _save_token_cache(cache: SerializableTokenCache) -> None:
    if cache.has_state_changed:
        TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_PATH.write_text(cache.serialize(), encoding="utf-8")


def _build_app(cache: SerializableTokenCache) -> PublicClientApplication:
    return PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )


#def _acquire_token(scopes: list[str] | None = None) -> str:
#    _require_env()
#    scopes = scopes or DEFAULT_SCOPES
#
#    cache = _load_token_cache()
#    app = _build_app(cache)
#
#    accounts = app.get_accounts()
#    result: dict[str, Any] | None = None
#
#    if accounts:
#        result = app.acquire_token_silent(scopes=scopes, account=accounts[0])
#
#    if not result:
#        log_event(f"interactive_login scopes={scopes}")
#        result = app.acquire_token_interactive(
#            scopes=scopes,
#            prompt="select_account",
#            domain_hint="organizations",
#        )
#
#    _save_token_cache(cache)
#
#    if not result or "access_token" not in result:
#        raise RuntimeError(f"Could not acquire token: {result}")
#
#    granted = result.get("scope")
#    log_event(f"token_acquired scopes={granted}")
#    return str(result["access_token"])

def _acquire_token(scopes: list[str] | None = None, force_interactive: bool = False) -> str:
    _require_env()
    scopes = scopes or DEFAULT_SCOPES

    result = _acquire_token_silent_only(scopes=scopes)

    if result and "access_token" in result:
        granted = result.get("scope")
        account = result.get("id_token_claims", {}).get("preferred_username")
        if account or granted:
            _write_token_info(
                {
                    "account": account,
                    "scope": granted,
                    "has_access_token": True,
                }
            )
        return str(result["access_token"])

    if not force_interactive:
        raise RuntimeError(
            "No valid cached SharePoint token is available. Run login_sharepoint first."
        )

    log_event(f"interactive_login scopes={scopes}")
    cache = _load_token_cache()
    app = _build_app(cache)

    result = app.acquire_token_interactive(
        scopes=scopes,
        prompt="select_account",
        domain_hint="organizations",
    )

    _save_token_cache(cache)

    if not result or "access_token" not in result:
        raise RuntimeError(f"Could not acquire token: {result}")

    granted = result.get("scope")
    account = result.get("id_token_claims", {}).get("preferred_username")
    _write_token_info(
        {
            "account": account,
            "scope": granted,
            "has_access_token": True,
        }
    )
    log_event(f"token_acquired scopes={granted} account={account}")
    return str(result["access_token"])

#def _graph_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
#    token = _acquire_token()
#    headers = {
#        "Authorization": f"Bearer {token}",
#        "Accept": "application/json",
#    }
#    url = f"{GRAPH_BASE}{path}"
#    resp = requests.get(url, headers=headers, params=params, timeout=60)
#    if resp.status_code >= 400:
#        raise RuntimeError(f"Graph GET {path} failed: {resp.status_code} {resp.text}")
#    return resp.json()

def _graph_get(path: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    token = _acquire_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = f"{GRAPH_BASE}{path}"
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph GET {path} failed: {resp.status_code} {resp.text}")
    return resp.json()


def _graph_get_bytes(url: str) -> bytes:
    token = _acquire_token()
    headers = {
        "Authorization": f"Bearer {token}",
    }
    resp = requests.get(url, headers=headers, timeout=120)
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph content download failed: {resp.status_code} {resp.text}")
    return resp.content


def _detect_text_encoding(data: bytes) -> str:
    detected = chardet.detect(data)
    return detected.get("encoding") or "utf-8"


def _read_text_like_bytes(data: bytes) -> str:
    encoding = _detect_text_encoding(data)
    try:
        return data.decode(encoding)
    except Exception:
        return data.decode("utf-8", errors="replace")


def _read_csv_bytes(data: bytes, max_rows: int = 100) -> str:
    encoding = _detect_text_encoding(data)
    text = data.decode(encoding, errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows: list[list[str]] = []
    for idx, row in enumerate(reader):
        if idx >= max_rows:
            rows.append(["... truncated ..."])
            break
        rows.append([str(cell) for cell in row])
    return "\n".join(" | ".join(row) for row in rows)


def _read_docx_bytes(data: bytes) -> str:
    with io.BytesIO(data) as bio:
        doc = DocxDocument(bio)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n\n".join(paragraphs)


def _read_pdf_bytes(data: bytes) -> str:
    with io.BytesIO(data) as bio:
        reader = PdfReader(bio)
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"[Page {i}]\n{text}")
    return "\n\n".join(pages)


def _read_pptx_bytes(data: bytes) -> str:
    with io.BytesIO(data) as bio:
        prs = Presentation(bio)
        slides_out = []
        for idx, slide in enumerate(prs.slides, start=1):
            parts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    text = shape.text.strip()
                    if text:
                        parts.append(text)
            if parts:
                slides_out.append(f"[Slide {idx}]\n" + "\n".join(parts))
    return "\n\n".join(slides_out)


def _read_xlsx_bytes(data: bytes, max_rows: int = 50, max_cols: int = 20) -> str:
    with io.BytesIO(data) as bio:
        wb = load_workbook(filename=bio, read_only=True, data_only=True)
        out = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            out.append(f"[Sheet: {sheet_name}]")
            row_count = 0
            for row in ws.iter_rows(values_only=True):
                if row_count >= max_rows:
                    out.append("... truncated ...")
                    break
                values = []
                for cell in row[:max_cols]:
                    values.append("" if cell is None else str(cell))
                if any(v != "" for v in values):
                    out.append(" | ".join(values))
                    row_count += 1
            out.append("")
    return "\n".join(out).strip()


def _extract_bytes_by_suffix(data: bytes, suffix: str) -> str:
    suffix = suffix.lower()

    if suffix in {".txt", ".md", ".json", ".yaml", ".yml", ".py", ".log"}:
        return _read_text_like_bytes(data)

    if suffix == ".csv":
        return _read_csv_bytes(data)

    if suffix == ".docx":
        return _read_docx_bytes(data)

    if suffix == ".pdf":
        return _read_pdf_bytes(data)

    if suffix == ".pptx":
        return _read_pptx_bytes(data)

    if suffix == ".xlsx":
        return _read_xlsx_bytes(data)

    raise ValueError(f"Unsupported document type: {suffix or 'no extension'}")


def _normalise_item(item: dict[str, Any]) -> dict[str, Any]:
    parent = item.get("parentReference", {}) or {}
    file_info = item.get("file", {}) or {}
    folder_info = item.get("folder", {}) or {}

    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "webUrl": item.get("webUrl"),
        "size": item.get("size"),
        "createdDateTime": item.get("createdDateTime"),
        "lastModifiedDateTime": item.get("lastModifiedDateTime"),
        "mimeType": file_info.get("mimeType"),
        "isFolder": bool(folder_info),
        "parentPath": parent.get("path"),
        "driveId": parent.get("driveId"),
    }

@mcp.tool()
def login_sharepoint() -> str:
    """Force interactive Microsoft login and cache tokens for later SharePoint calls."""
    log_event("login_sharepoint")
    _acquire_token(force_interactive=True)
    info = _read_token_info()
    return f"SharePoint login successful. Account={info.get('account')} Scopes={info.get('scope')}"


@mcp.tool()
def sharepoint_auth_status() -> dict[str, Any]:
    """Return SharePoint auth status without forcing interactive login."""
    log_event("sharepoint_auth_status")

    info = _read_token_info()
    cache = _load_token_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()

    silent_result = None
    has_valid_silent_token = False
    silent_error = None

    if accounts:
        silent_result = app.acquire_token_silent(scopes=DEFAULT_SCOPES, account=accounts[0])
        if silent_result and "access_token" in silent_result:
            has_valid_silent_token = True
        elif silent_result:
            silent_error = silent_result.get("error_description") or str(silent_result)

    return {
        "has_cached_token_info": bool(info),
        "account": info.get("account"),
        "scopes": info.get("scope"),
        "cached_accounts": [a.get("username") for a in accounts],
        "has_valid_silent_token": has_valid_silent_token,
        "silent_error": silent_error,
    }

@mcp.tool()
def who_am_i() -> dict[str, Any]:
    """Return basic information about the signed-in Microsoft Graph user."""
    log_event("who_am_i")
    return _graph_get("/me")


#@mcp.tool()
#def list_sites(query: str = "*", max_hits: int = 10) -> list[dict[str, Any]]:
#    """Search SharePoint sites visible to the signed-in user."""
#    log_event(f"list_sites query={query!r} max_hits={max_hits}")
#    data = _graph_get("/sites", params={"search": query})
#    values = data.get("value", [])[:max_hits]
#    return [
#        {
#            "id": site.get("id"),
#            "name": site.get("name"),
#            "displayName": site.get("displayName"),
#            "webUrl": site.get("webUrl"),
#            "description": site.get("description"),
#            "hostname": (site.get("siteCollection") or {}).get("hostname"),
#        }
#        for site in values
#    ]

@mcp.tool()
def list_sites(query: str = "*", max_hits: int = 10) -> list[dict[str, Any]]:
    log_event(f"list_sites query={query!r} max_hits={max_hits}")
    data = _graph_get("/sites", params={"search": query}, timeout=90)
    values = data.get("value", [])[:max_hits]
    return [
        {
            "id": site.get("id"),
            "name": site.get("name"),
            "displayName": site.get("displayName"),
            "webUrl": site.get("webUrl"),
            "description": site.get("description"),
            "hostname": (site.get("siteCollection") or {}).get("hostname"),
        }
        for site in values
    ]


@mcp.tool()
def list_my_drives() -> list[dict[str, Any]]:
    """List drives visible under the signed-in user's account."""
    log_event("list_my_drives")
    data = _graph_get("/me/drives")
    return [
        {
            "id": drive.get("id"),
            "name": drive.get("name"),
            "description": drive.get("description"),
            "webUrl": drive.get("webUrl"),
            "driveType": drive.get("driveType"),
        }
        for drive in data.get("value", [])
    ]


@mcp.tool()
def list_site_drives(site_id: str) -> list[dict[str, Any]]:
    """List drives in a SharePoint site."""
    log_event(f"list_site_drives site_id={site_id}")
    data = _graph_get(f"/sites/{site_id}/drives")
    return [
        {
            "id": drive.get("id"),
            "name": drive.get("name"),
            "description": drive.get("description"),
            "webUrl": drive.get("webUrl"),
            "driveType": drive.get("driveType"),
        }
        for drive in data.get("value", [])
    ]


@mcp.tool()
def list_drive_items(drive_id: str, item_id: str = "root", max_items: int = 50) -> list[dict[str, Any]]:
    """List items under a drive folder. Use item_id='root' for the drive root."""
    log_event(f"list_drive_items drive_id={drive_id} item_id={item_id} max_items={max_items}")
    data = _graph_get(f"/drives/{drive_id}/items/{item_id}/children")
    values = data.get("value", [])[:max_items]
    return [_normalise_item(item) for item in values]


#@mcp.tool()
#def search_drive_documents(drive_id: str, query: str, max_hits: int = 20) -> list[dict[str, Any]]:
#    """Search for documents within a drive."""
#    log_event(f"search_drive_documents drive_id={drive_id} query={query!r} max_hits={max_hits}")
#    encoded = quote(query, safe="")
#    data = _graph_get(f"/drives/{drive_id}/root/search(q='{encoded}')")
#    values = data.get("value", [])[:max_hits]
#    return [_normalise_item(item) for item in values]

@mcp.tool()
def search_drive_documents(drive_id: str, query: str, max_hits: int = 20) -> list[dict[str, Any]]:
    log_event(f"search_drive_documents drive_id={drive_id} query={query!r} max_hits={max_hits}")
    encoded = quote(query, safe="")
    data = _graph_get(f"/drives/{drive_id}/root/search(q='{encoded}')", timeout=90)
    values = data.get("value", [])[:max_hits]
    return [_normalise_item(item) for item in values]

#@mcp.tool()
#def search_site_drive_documents(site_id: str, query: str, max_hits: int = 20) -> list[dict[str, Any]]:
#    """Search for documents in the default document library of a SharePoint site."""
#    log_event(f"search_site_drive_documents site_id={site_id} query={query!r} max_hits={max_hits}")
#    encoded = quote(query, safe="")
#    data = _graph_get(f"/sites/{site_id}/drive/root/search(q='{encoded}')")
#    values = data.get("value", [])[:max_hits]
#    return [_normalise_item(item) for item in values]

@mcp.tool()
def search_site_drive_documents(site_id: str, query: str, max_hits: int = 20) -> list[dict[str, Any]]:
    log_event(f"search_site_drive_documents site_id={site_id} query={query!r} max_hits={max_hits}")
    encoded = quote(query, safe="")
    data = _graph_get(f"/sites/{site_id}/drive/root/search(q='{encoded}')", timeout=90)
    values = data.get("value", [])[:max_hits]
    return [_normalise_item(item) for item in values]

@mcp.tool()
def get_sharepoint_document_metadata(drive_id: str, item_id: str) -> dict[str, Any]:
    """Return metadata for a SharePoint drive item."""
    log_event(f"get_sharepoint_document_metadata drive_id={drive_id} item_id={item_id}")
    item = _graph_get(f"/drives/{drive_id}/items/{item_id}")
    return _normalise_item(item)


@mcp.tool()
def read_sharepoint_document(drive_id: str, item_id: str) -> str:
    """Download and extract text from a supported SharePoint document."""
    log_event(f"read_sharepoint_document drive_id={drive_id} item_id={item_id}")

    item = _graph_get(f"/drives/{drive_id}/items/{item_id}")
    name = str(item.get("name") or "")
    suffix = Path(name).suffix.lower()

    if not suffix:
        raise ValueError(f"Cannot determine file type for item name: {name}")

    content_url = f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content"
    data = _graph_get_bytes(content_url)

    extracted = _extract_bytes_by_suffix(data, suffix)
    return extracted if extracted.strip() else f"[No readable text extracted from {name}]"


_configure_mcp_logging()

if __name__ == "__main__":
    mcp.run()
