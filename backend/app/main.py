from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db.models import Product
from app.db.session import SessionLocal, init_db
from app.routes import admin, query, sessions, voice
from app.routes.admin import limiter

settings = get_settings()

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_products()
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
