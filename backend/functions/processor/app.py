import json
import os
from datetime import datetime, timezone

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def now():
    return datetime.now(timezone.utc).isoformat()


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    failures = []
    for record in event.get("Records", []):
        try:
            job = json.loads(record["body"])
            if job.get("type") != "PROCESS_EVIDENCE":
                raise ValueError("Unsupported evidence job type")
            case_id = job["caseId"]
            evidence_id = job["evidenceId"]
            logger.info(
                "Processing evidence job",
                extra={"caseId": case_id, "evidenceId": evidence_id},
            )
            # Core processing only records durable receipt. Metadata extraction,
            # thumbnails, Textract and Bedrock remain explicit future extensions.
            stamp = now()
            table.update_item(
                Key={"PK": f"CASE#{case_id}", "SK": f"EVIDENCE#{evidence_id}"},
                UpdateExpression="SET #status = :status, processedAt = :stamp",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "PROCESSED", ":stamp": stamp},
                ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
            )
            table.put_item(
                Item={
                    "PK": f"CASE#{case_id}",
                    "SK": f"PROCESSING#{evidence_id}",
                    "eventType": "EvidenceProcessed",
                    "evidenceId": evidence_id,
                    "createdAt": stamp,
                }
            )
        except Exception:
            logger.exception("Evidence job failed")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
