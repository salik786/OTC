import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db.models import Document, Product
from app.db.session import SessionLocal, init_db
from app.rag.ingest import ingest_document
from app.routes import admin, query, sessions, voice
from app.routes.admin import limiter

logger = logging.getLogger("otc.startup")
settings = get_settings()

# Deliberately NOT under settings.corpus_dir ("./data/corpus") - that path lives inside the
# Railway volume mounted at ./data for the FAISS index/DB, and a freshly provisioned volume is
# empty and SHADOWS whatever was baked into the container image at that path. Pointing the seed
# source here (outside the mount) is what makes it actually survive a fresh volume.
SEED_CORPUS_DIR = Path(__file__).resolve().parent.parent / "seed_corpus"

SEED_PRODUCTS = [
    ("paracetamol", "Paracetamol 500mg Tablets"),
    ("multivitamin", "Daily Multivitamin"),
]


def _seed_products() -> None:
    db = SessionLocal()
    try:
        for slug, display_name in SEED_PRODUCTS:
            if not db.query(Product).filter(Product.slug == slug).first():
                db.add(Product(slug=slug, display_name=display_name))
        db.commit()
    finally:
        db.close()


def _seed_corpus() -> None:
    """The vector index and Chunk/Document rows live on the Railway volume (SQLite file + FAISS
    index dir) - every fresh volume starts empty, even though ingestion previously happened via
    the admin panel. Without this, /api/query and /api/core-info silently return zero retrieved
    chunks (and deflect on every question) until someone re-uploads leaflets by hand. Bootstraps
    from SEED_CORPUS_DIR (baked into the git-committed image, outside the volume mount so it can't
    be shadowed), only for products that don't already have an active document (so a real
    admin-uploaded leaflet is never overwritten by the placeholder)."""
    db = SessionLocal()
    try:
        for slug, _ in SEED_PRODUCTS:
            product = db.query(Product).filter(Product.slug == slug).first()
            if product is None:
                continue
            has_active_doc = db.query(Document).filter(Document.product_id == product.id, Document.active == True).first()  # noqa: E712
            if has_active_doc:
                logger.info("corpus seed: %s already has an active document, skipping", slug)
                continue
            corpus_path = SEED_CORPUS_DIR / f"{slug}_placeholder.txt"
            if not corpus_path.exists():
                logger.warning("corpus seed: no placeholder file at %s for %s - product will have zero retrievable content", corpus_path, slug)
                continue
            ingest_document(db, slug, corpus_path.name, corpus_path.read_bytes())
            logger.info("corpus seed: ingested placeholder leaflet for %s", slug)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_products()
    _seed_corpus()
    yield


app = FastAPI(title="OTC Medication Guidance API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(query.router)
app.include_router(voice.router)
app.include_router(admin.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
