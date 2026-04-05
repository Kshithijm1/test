import time
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.controller import router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    log.info("=" * 80)
    log.info("🚀 Backend server starting up...")
    log.info("=" * 80)
    start = time.time()
    # Pre-warm imports and connections here if needed
    elapsed = time.time() - start
    log.info(f"✅ Backend ready in {elapsed:.2f}s")
    log.info("=" * 80)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)