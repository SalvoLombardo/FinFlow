import asyncio
import json
import uuid

from sqlalchemy import text

from deps import Session, SQSEvent, logger
from providers import SYSTEM_PROMPT, generate


def lambda_handler(event, context):
    return asyncio.run(_handler(event))


async def _handler(event: dict) -> dict:
    batch_item_failures = []
    for record in event["Records"]:
        try:
            body = json.loads(record["body"])
            raw = json.loads(body["Message"])
            await _process(SQSEvent(**raw))
        except Exception as exc:
            logger.error("Failed %s: %s", record["messageId"], exc, exc_info=True)
            batch_item_failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": batch_item_failures}


async def _process(ev: SQSEvent) -> None:
    user_uuid = uuid.UUID(ev.user_id)

    async with Session() as session:
        # --- Load AI settings ---
        row = await session.execute(
            text(
                "SELECT ai_enabled, ai_mode, ai_provider, ai_model, "
                "       api_key_enc, ollama_url, ollama_model "
                "FROM user_ai_settings WHERE user_id = :uid"
            ),
            {"uid": user_uuid},
        )
        ai_cfg = row.mappings().one_or_none()

        if not ai_cfg or not ai_cfg["ai_enabled"]:
            logger.info("AI not enabled for user %s — skipping", ev.user_id)
            return

        # --- Build prompt based on event type ---
        insight_type = ev.payload.get("insight_type", "savings_tip")

        if ev.event_type in ("budget.updated", "week.closed"):
            prompt, insight_type = await _prompt_weekly(session, user_uuid, ev.payload)
        else:
            # ai.analysis.requested
            prompt, insight_type = await _prompt_savings_tip(session, user_uuid, insight_type)

        # --- Call AI provider ---
        content = await generate(
            ai_mode=ai_cfg["ai_mode"],
            ai_provider=ai_cfg["ai_provider"],
            api_key_enc=ai_cfg["api_key_enc"],
            ai_model=ai_cfg["ai_model"],
            ollama_url=ai_cfg["ollama_url"] or "http://localhost:11434",
            ollama_model=ai_cfg["ollama_model"] or "llama3.2",
            prompt=prompt,
        )
        model_label = ai_cfg["ai_model"] or ai_cfg["ai_provider"] or "ollama"

        # --- Persist insight ---
        await session.execute(
            text(
                "INSERT INTO ai_insights "
                "  (id, user_id, insight_type, content, model_used, is_read) "
                "VALUES (:id, :uid, :itype, :content, :model, false)"
            ),
            {
                "id": str(uuid.uuid4()),
                "uid": str(user_uuid),
                "itype": insight_type,
                "content": content,
                "model": model_label,
            },
        )
        await session.commit()

    logger.info(
        "Insight saved — event_type=%s user=%s insight_type=%s",
        ev.event_type,
        ev.user_id,
        insight_type,
    )


async def _prompt_weekly(session, user_uuid: uuid.UUID, payload: dict):
    """Build weekly insight prompt from week data."""
    week_id = payload.get("week_id")
    insight_type = "weekly_insight"

    if not week_id:
        return await _prompt_savings_tip(session, user_uuid, insight_type)

    row = await session.execute(
        text(
            "SELECT week_start, week_end, opening_balance "
            "FROM financial_weeks WHERE id = :wid AND user_id = :uid"
        ),
        {"wid": week_id, "uid": user_uuid},
    )
    week = row.mappings().one_or_none()
    if not week:
        return await _prompt_savings_tip(session, user_uuid, "savings_tip")

    txs = await session.execute(
        text(
            "SELECT type, amount, category FROM transactions "
            "WHERE week_id = :wid AND user_id = :uid"
        ),
        {"wid": week_id, "uid": user_uuid},
    )
    transactions = txs.mappings().all()

    total_income = sum(float(t["amount"]) for t in transactions if t["type"] == "income")
    total_expense = sum(float(t["amount"]) for t in transactions if t["type"] == "expense")
    closing = float(week["opening_balance"]) + total_income - total_expense

    cat_totals: dict[str, float] = {}
    for t in transactions:
        if t["type"] == "expense" and t["category"]:
            cat_totals[t["category"]] = cat_totals.get(t["category"], 0) + float(t["amount"])
    top_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:3]
    cats_str = ", ".join(f"{c} (€{a:.0f})" for c, a in top_cats) or "nessuna"

    week_label = str(week["week_start"])
    prompt = (
        f"Settimana del {week_label}:\n"
        f"- Saldo apertura: €{float(week['opening_balance']):.2f}\n"
        f"- Entrate: €{total_income:.2f}   Uscite: €{total_expense:.2f}\n"
        f"- Saldo chiusura: €{closing:.2f}\n"
        f"- Categorie principali: {cats_str}\n\n"
        "Dimmi qualcosa di utile su questa settimana."
    )
    return prompt, insight_type


async def _prompt_savings_tip(session, user_uuid: uuid.UUID, insight_type: str):
    """Build savings tip prompt from last 8 weeks of data."""
    rows = await session.execute(
        text(
            "SELECT id, opening_balance FROM financial_weeks "
            "WHERE user_id = :uid ORDER BY week_start DESC LIMIT 8"
        ),
        {"uid": user_uuid},
    )
    weeks = rows.mappings().all()

    if not weeks:
        prompt = (
            "L'utente ha appena iniziato a usare FinFlow. "
            "Dagli un consiglio di benvenuto su come tenere traccia delle spese settimanali."
        )
        return prompt, insight_type

    week_ids = [str(w["id"]) for w in weeks]
    placeholders = ", ".join(f":wid{i}" for i in range(len(week_ids)))
    params = {f"wid{i}": wid for i, wid in enumerate(week_ids)}
    params["uid"] = user_uuid

    txs = await session.execute(
        text(
            f"SELECT type, amount, category FROM transactions "
            f"WHERE week_id IN ({placeholders}) AND user_id = :uid"
        ),
        params,
    )
    transactions = txs.mappings().all()

    n = len(weeks)
    total_income = sum(float(t["amount"]) for t in transactions if t["type"] == "income")
    total_expense = sum(float(t["amount"]) for t in transactions if t["type"] == "expense")
    avg_income = total_income / n
    avg_expense = total_expense / n

    cat_totals: dict[str, float] = {}
    for t in transactions:
        if t["type"] == "expense" and t["category"]:
            cat_totals[t["category"]] = cat_totals.get(t["category"], 0) + float(t["amount"])
    top_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    cats_str = ", ".join(f"{c} (€{a:.0f})" for c, a in top_cats) or "nessuna"
    net = avg_income - avg_expense

    prompt = (
        f"Ultime {n} settimane analizzate:\n"
        f"- Media entrate settimanali: €{avg_income:.2f}\n"
        f"- Media uscite settimanali: €{avg_expense:.2f}\n"
        f"- Risparmio netto medio: €{net:.2f}\n"
        f"- Principali categorie di spesa: {cats_str}\n\n"
        "Dammi un consiglio pratico per risparmiare di più."
    )
    return prompt, insight_type
