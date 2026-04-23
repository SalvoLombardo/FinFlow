import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Phase 2 / Phase 5: full implementation
# Triggered by: ai.analysis.requested, budget.updated
# Loads user_ai_settings, instantiates AI provider, generates insight, saves to ai_insights


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
    raise NotImplementedError("Implement in Phase 2/5")
