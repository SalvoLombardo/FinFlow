from fastapi import APIRouter

router = APIRouter()

# Phase 1.4: GET /, POST /, GET /{week_id}, PUT /{week_id}
# PUT /{week_id} closing a week publishes WEEK_CLOSED to SNS (Phase 2)
