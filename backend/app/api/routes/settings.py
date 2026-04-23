from fastapi import APIRouter

router = APIRouter()

# Phase 1.4 / Phase 5: GET /ai, PUT /ai, POST /ai/test
# API key stored encrypted with Fernet (ENCRYPTION_KEY env var)
