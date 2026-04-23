from fastapi import APIRouter

router = APIRouter()

# Phase 1.4: GET /, POST /, PUT /{id}, DELETE /{id}
# query params: week_id, type, category
# Publishes BUDGET_UPDATED to SNS after write (Phase 2)
