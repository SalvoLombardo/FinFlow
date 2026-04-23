import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Phase 2: full implementation
# Triggered by: budget.updated, week.closed
# Recalculates 8-week projections and updates closing_balance + goal current_amount


def lambda_handler(event, context):
    batch_item_failures = []
    for record in event["Records"]:
        try:
            message = json.loads(record["body"])
            sns_message = json.loads(message["Message"])
            process(sns_message)
        except Exception as e:
            logger.error(f"Failed {record['messageId']}: {e}")
            batch_item_failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": batch_item_failures}


def process(event: dict) -> None:
    raise NotImplementedError("Implement in Phase 2")
