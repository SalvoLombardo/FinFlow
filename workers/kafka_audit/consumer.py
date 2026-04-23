# Phase 3: full implementation
# Reads batches of 100 messages, accumulates for 5 min, writes to S3 as audit/YYYY/MM/DD/HH-MM-SS.jsonl
# Falls back to local audit_archive/ when S3_AUDIT_BUCKET is empty
# Handles SIGTERM gracefully


async def run_consumer() -> None:
    raise NotImplementedError("Implement in Phase 3")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_consumer())
