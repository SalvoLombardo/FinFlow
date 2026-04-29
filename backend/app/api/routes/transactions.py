import asyncio
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.audit.kafka_producer import AuditEvent, audit_producer
from app.core.database import get_db
from app.events.schemas import EventType, FinFlowEvent
from app.messaging.sns_publisher import sns_publisher
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate
from app.services.weeks import get_or_create_week

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    week_id: uuid.UUID | None = Query(default=None),
    type: TransactionType | None = Query(default=None),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Transaction).where(Transaction.user_id == current_user.id)
    if week_id is not None:
        q = q.where(Transaction.week_id == week_id)
    if type is not None:
        q = q.where(Transaction.type == type)
    if category is not None:
        q = q.where(Transaction.category == category)
    result = await db.execute(q.order_by(Transaction.created_at))
    return result.scalars().all()


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    request: Request,
    body: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tx_date = body.transaction_date or date.today()
    week = await get_or_create_week(current_user.id, tx_date, db)

    data = body.model_dump()
    data["transaction_date"] = tx_date
    tx = Transaction(**data, user_id=current_user.id, week_id=week.id)
    db.add(tx)
    await db.flush()

    await sns_publisher.publish(
        FinFlowEvent(
            event_type=EventType.BUDGET_UPDATED,
            user_id=str(current_user.id),
            payload={"week_id": str(week.id)},
        )
    )
    asyncio.create_task(
        audit_producer.send(
            AuditEvent(
                user_id=str(current_user.id),
                action="transaction.created",
                entity_type="transaction",
                entity_id=str(tx.id),
                after_state=TransactionRead.model_validate(tx).model_dump(mode="json"),
                ip_address=_client_ip(request),
            )
        )
    )
    return tx


@router.put("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: uuid.UUID,
    request: Request,
    body: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    before = TransactionRead.model_validate(tx).model_dump(mode="json")

    # If the date changes, move the transaction to the correct week.
    updates = body.model_dump(exclude_unset=True)
    if "transaction_date" in updates:
        week = await get_or_create_week(current_user.id, updates["transaction_date"], db)
        tx.week_id = week.id

    for field, value in updates.items():
        setattr(tx, field, value)

    await sns_publisher.publish(
        FinFlowEvent(
            event_type=EventType.BUDGET_UPDATED,
            user_id=str(current_user.id),
            payload={"week_id": str(tx.week_id)},
        )
    )
    asyncio.create_task(
        audit_producer.send(
            AuditEvent(
                user_id=str(current_user.id),
                action="transaction.updated",
                entity_type="transaction",
                entity_id=str(tx.id),
                before_state=before,
                after_state=TransactionRead.model_validate(tx).model_dump(mode="json"),
                ip_address=_client_ip(request),
            )
        )
    )
    return tx


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    before = TransactionRead.model_validate(tx).model_dump(mode="json")
    await db.delete(tx)
    asyncio.create_task(
        audit_producer.send(
            AuditEvent(
                user_id=str(current_user.id),
                action="transaction.deleted",
                entity_type="transaction",
                entity_id=str(transaction_id),
                before_state=before,
                after_state={"deleted": True},
                ip_address=_client_ip(request),
            )
        )
    )
