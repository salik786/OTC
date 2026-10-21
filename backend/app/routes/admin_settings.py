"""Admin API for the versioned RAG configuration: view/edit/restore settings, re-index, and try a
configuration (a single question, or the whole boundary suite) before - or after - saving it."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.auth import require_admin
from app.db.models import Document, Product, RagConfigVersion
from app.db.session import SessionLocal, get_db
from app.rag.boundary_cases import CASES
from app.rag.config_store import (
    CHUNKING_STRATEGIES, DEFAULT_CONFIG, EMBEDDING_MODELS, FIELDS, REINDEX_KEYS, ConfigError,
    activate_version, get_active_config, invalidate_cache, merged, reindex_keys_changed, save_version,
)
from app.rag.generate import generate_answer
from app.rag.ingest import reindex_all
from app.rag.retrieve import retrieve
from app.rag.vectorstore import get_vectorstore
from app.routes.admin import limiter

logger = logging.getLogger("otc.admin.settings")
router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"], dependencies=[Depends(require_admin)])


class SettingsUpdate(BaseModel):
    config: dict
    note: str = ""


class TestRequest(BaseModel):
    product_slug: str
    query_text: str
    config: dict | None = None  # unsaved overrides applied on top of the active config


class RegressionRequest(BaseModel):
    product_slug: str = "paracetamol"
    config: dict | None = None


def _version_out(row: RagConfigVersion, include_config: bool = False) -> dict:
    out = {
        "version": row.version, "note": row.note, "created_by": row.created_by,
        "created_at": row.created_at.isoformat(), "is_active": row.is_active,
    }
    if include_config:
        out["config"] = row.config
    return out


def _bad_request(e: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


@router.get("")
def get_settings_overview(db: DBSession = Depends(get_db)) -> dict:
    active = get_active_config(db)
    row = db.query(RagConfigVersion).filter(RagConfigVersion.version == active.version).first()
    vs = get_vectorstore()
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return {
        "active": _version_out(row, include_config=True) | {"config": active.config},
        "defaults": DEFAULT_CONFIG,
        "fields": FIELDS,
        "chunking_strategies": CHUNKING_STRATEGIES,
        "embedding_dims": EMBEDDING_MODELS,
        "index": {
            **vs.meta,
            "chunk_count": len(vs.chunk_ids),
            "documents": [
                {"filename": d.filename, "chunk_count": d.chunk_count, "source_reconstructed": bool(d.source_reconstructed)}
                for d in docs
            ],
        },
        # Which saved settings don't match how the live index was actually built yet.
        "pending_reindex": [k for k in REINDEX_KEYS if vs.meta.get(k) != active.config[k]],
    }


@router.put("")
def update_settings(req: SettingsUpdate, admin_user: str = Depends(require_admin), db: DBSession = Depends(get_db)) -> dict:
    try:
        before = get_active_config(db).config
        row = save_version(db, req.config, req.note, admin_user)
    except ConfigError as e:
        raise _bad_request(e)
    return {"version": _version_out(row, include_config=True), "needs_reindex": reindex_keys_changed(before, row.config)}


@router.get("/versions")
def list_versions(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(RagConfigVersion).order_by(RagConfigVersion.version.desc()).all()
    return [_version_out(r, include_config=True) for r in rows]


@router.post("/versions/{version}/activate")
def restore_version(version: int, db: DBSession = Depends(get_db)) -> dict:
    try:
        before = get_active_config(db).config
        row = activate_version(db, version)
    except ConfigError as e:
        raise _bad_request(e)
    return {"version": _version_out(row, include_config=True), "needs_reindex": reindex_keys_changed(before, row.config)}


@router.post("/reindex")
@limiter.limit("3/minute")
def reindex(request: Request, db: DBSession = Depends(get_db)) -> dict:
    """Re-chunk every leaflet from its stored text and re-embed with the ACTIVE config's chunking and
    embedding settings. All-or-nothing: on failure the existing chunks/index keep serving."""
    cfg = get_active_config(db)
    started = time.perf_counter()
    try:
        result = reindex_all(db, cfg)
    except ValueError as e:
        raise _bad_request(e)
    except Exception as e:  # embedding API failure, bad model, etc. - nothing was changed
        logger.exception("re-index failed")
        raise HTTPException(status_code=502, detail=f"Re-index failed and nothing was changed: {e}")
    invalidate_cache()
    return {**result, "seconds": round(time.perf_counter() - started, 1), "config_version": cfg.version}


def _answer(db: DBSession, product: Product, query_text: str, cfg: dict) -> dict:
    chunks = retrieve(db, query_text, product_id=product.id, top_k=cfg["top_k"])
    answer = generate_answer(query_text, chunks, product.display_name, [], cfg)
    return {
        "answer_text": answer,
        "in_scope": answer.strip() != cfg["fallback_text"],
        "retrieved_chunks": [
            {"section_label": c["section_label"], "score": c["score"], "text": c["text"],
             "document_filename": c.get("document_filename")} for c in chunks
        ],
    }


def _product_or_404(db: DBSession, slug: str) -> Product:
    product = db.query(Product).filter(Product.slug == slug).first()
    if product is None:
        raise HTTPException(status_code=404, detail=f"unknown product_slug '{slug}'")
    return product


@router.post("/test")
@limiter.limit("30/minute")
def test_question(request: Request, req: TestRequest, db: DBSession = Depends(get_db)) -> dict:
    """Answer one question under the active config plus any UNSAVED overrides. Nothing is logged -
    no session or turn is created - so trying settings never pollutes research data."""
    product = _product_or_404(db, req.product_slug)
    try:
        cfg = merged(get_active_config(db).config, req.config)
    except ConfigError as e:
        raise _bad_request(e)
    start = time.perf_counter()
    result = _answer(db, product, req.query_text, cfg)
    result["latency_ms"] = (time.perf_counter() - start) * 1000
    ignored = [k for k in reindex_keys_changed(get_vectorstore().meta, cfg)]
    if ignored:
        result["note"] = ("Chunking/embedding settings that differ from the live index ("
                          + ", ".join(ignored) + ") are not applied here until you re-index.")
    return result


@router.post("/regression")
@limiter.limit("6/minute")
def run_boundary_suite(request: Request, req: RegressionRequest, db: DBSession = Depends(get_db)) -> dict:
    """Run the study's boundary cases (must-answer and must-refuse questions) under the active config
    plus any unsaved overrides, so a prompt/model/top-k change can be checked before it's saved.
    Nothing is logged."""
    product = _product_or_404(db, req.product_slug)
    try:
        cfg = merged(get_active_config(db).config, req.config)
    except ConfigError as e:
        raise _bad_request(e)

    def run_case(case: tuple[str, bool]) -> dict:
        query, expected = case
        session = SessionLocal()  # one DB session per worker thread
        try:
            r = _answer(session, session.query(Product).filter(Product.id == product.id).first(), query, cfg)
        finally:
            session.close()
        return {"query": query, "expected_in_scope": expected, "in_scope": r["in_scope"],
                "passed": r["in_scope"] == expected, "answer_text": r["answer_text"]}

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(run_case, CASES))
    return {"passed": sum(r["passed"] for r in results), "total": len(results), "results": results}
