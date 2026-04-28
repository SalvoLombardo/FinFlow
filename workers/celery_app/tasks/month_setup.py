import asyncio
import calendar
import datetime as _dt
import logging
import uuid
from decimal import Decimal

from celery_app.config import app
from celery_app.db import FinancialWeek, Transaction, TransactionType, User, UserFinancialSettings, get_session
from kafka_audit.producer import AuditEvent, KafkaAuditProducer

logger = logging.getLogger(__name__)

_audit_producer = KafkaAuditProducer()


def _today() -> _dt.date:
    return _dt.date.today()


def _next_month(today: _dt.date) -> tuple[int, int]:
    if today.month == 12:
        return today.year + 1, 1
    return today.year, today.month + 1


def _week_ranges(year: int, month: int) -> list[tuple[_dt.date, _dt.date]]:
    """Return (week_start, week_end) pairs for all Mon-Sun weeks starting in month."""
    first = _dt.date(year, month, 1)
    last = _dt.date(year, month, calendar.monthrange(year, month)[1])
    days_to_monday = (7 - first.weekday()) % 7
    monday = first + _dt.timedelta(days=days_to_monday)
    ranges: list[tuple[_dt.date, _dt.date]] = []
    while monday <= last:
        ranges.append((monday, monday + _dt.timedelta(days=6)))
        monday += _dt.timedelta(weeks=1)
    return ranges


def _send_audit(event: AuditEvent) -> None:
    try:
        asyncio.run(_audit_producer.send(event))
    except Exception as exc:
        logger.warning("Kafka audit skipped — %s", exc)


@app.task(bind=True, max_retries=3)
def create_next_month_weeks(self):
    """Create financial_weeks for next month for all users; copy recurring transactions; log to Kafka."""
    today = _today()
    year, month = _next_month(today)
    ranges = _week_ranges(year, month)

    if not ranges:
        logger.info("month_setup: no weeks to create for %d-%02d", year, month)
        return {"created": 0, "month": f"{year}-{month:02d}"}

    created = 0
    try:
        with get_session() as session:
            users = session.query(User).all()

            for user in users:
                last_week = (
                    session.query(FinancialWeek)
                    .filter(FinancialWeek.user_id == user.id)
                    .order_by(FinancialWeek.week_start.desc())
                    .first()
                )

                if last_week:
                    # Compute closing of last week from actual transactions.
                    txs = session.query(Transaction).filter(Transaction.week_id == last_week.id).all()
                    net = sum(
                        (t.amount if t.type == TransactionType.income else -t.amount for t in txs),
                        Decimal("0"),
                    )
                    carry = (last_week.opening_balance + net) if txs else (
                        last_week.closing_balance if last_week.closing_balance is not None
                        else last_week.opening_balance
                    )
                else:
                    ufs = session.query(UserFinancialSettings).filter(
                        UserFinancialSettings.user_id == user.id
                    ).first()
                    carry = ufs.initial_balance if ufs else Decimal("0")

                recurring = (
                    session.query(Transaction)
                    .filter(Transaction.week_id == last_week.id, Transaction.is_recurring.is_(True))
                    .all()
                    if last_week
                    else []
                )

                running_carry = carry
                for idx, (week_start, week_end) in enumerate(ranges):
                    exists = (
                        session.query(FinancialWeek)
                        .filter(
                            FinancialWeek.user_id == user.id,
                            FinancialWeek.week_start == week_start,
                        )
                        .first()
                    )
                    if exists:
                        # Propagate carry even for existing weeks.
                        running_carry = (
                            exists.closing_balance if exists.closing_balance is not None
                            else exists.opening_balance
                        )
                        continue

                    new_week = FinancialWeek(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        week_start=week_start,
                        week_end=week_end,
                        opening_balance=running_carry,
                    )
                    session.add(new_week)
                    session.flush()

                    # Copy recurring transactions only into the first new week.
                    if idx == 0:
                        for txn in recurring:
                            session.add(
                                Transaction(
                                    id=uuid.uuid4(),
                                    user_id=user.id,
                                    week_id=new_week.id,
                                    name=txn.name,
                                    amount=txn.amount,
                                    type=txn.type,
                                    category=txn.category,
                                    is_recurring=True,
                                    recurrence_rule=txn.recurrence_rule,
                                    transaction_date=week_start,
                                    notes=txn.notes,
                                )
                            )
                        # Advance carry by the net of recurring transactions.
                        rec_net = sum(
                            (t.amount if t.type == TransactionType.income else -t.amount for t in recurring),
                            Decimal("0"),
                        )
                        running_carry = running_carry + rec_net
                    # Weeks 2+ have no transactions yet; carry is unchanged.

                    created += 1
                    _send_audit(
                        AuditEvent(
                            user_id=str(user.id),
                            action="week.created",
                            entity_type="financial_week",
                            entity_id=str(new_week.id),
                            after_state={
                                "week_start": week_start.isoformat(),
                                "week_end": week_end.isoformat(),
                                "opening_balance": str(new_week.opening_balance),
                            },
                        )
                    )

            session.commit()

    except Exception as exc:
        logger.error("month_setup failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)

    logger.info("month_setup: created %d weeks for %d-%02d", created, year, month)
    return {"created": created, "month": f"{year}-{month:02d}"}
