import base64
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger()
tracer = Tracer()
metrics = Metrics()
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
s3 = boto3.client("s3")
sqs = boto3.client("sqs")
BUCKET = os.environ["EVIDENCE_BUCKET"]
QUEUE = os.environ["PROCESSING_QUEUE_URL"]
ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "audio/webm": "webm",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "application/pdf": "pdf",
}
MAX_EVIDENCE_BYTES = 20 * 1024 * 1024


def response(status, payload):
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
            "access-control-allow-origin": os.getenv("ALLOWED_ORIGIN", "*"),
            "x-content-type-options": "nosniff",
        },
        "body": json.dumps(
            payload,
            default=lambda value: float(value) if isinstance(value, Decimal) else str(value),
        ),
    }


def request_body(event):
    try:
        payload = json.loads(event.get("body") or "{}")
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def request_headers(event):
    return {str(key).lower(): value for key, value in (event.get("headers") or {}).items()}


def identity(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    return claims.get("sub"), claims.get("cognito:groups", "")


def has_group(groups, expected):
    if isinstance(groups, list):
        return expected in groups
    value = str(groups).strip()
    if value.startswith("["):
        try:
            return expected in json.loads(value)
        except json.JSONDecodeError:
            pass
    return expected in {part.strip().strip('"') for part in value.split(",")}


def now():
    return datetime.now(timezone.utc).isoformat()


def get_case_metadata(case_id):
    return table.get_item(Key={"PK": f"CASE#{case_id}", "SK": "METADATA"}).get("Item")


def owner_or_reviewer(case_record, user_id, groups):
    return case_record and (
        (case_record.get("userId") == user_id and has_group(groups, "Farmers"))
        or has_group(groups, "Reviewers")
    )


def append_event(case_id, event_type, actor_id, **details):
    stamp = now()
    item = {
        "PK": f"CASE#{case_id}",
        "SK": f"EVENT#{stamp}#{uuid.uuid4().hex[:8]}",
        "eventType": event_type,
        "actorId": actor_id,
        "createdAt": stamp,
        **details,
    }
    table.put_item(Item=item)
    return stamp


def create_case(event, user_id, groups):
    if not has_group(groups, "Farmers") or has_group(groups, "Reviewers"):
        return response(403, {"message": "Farmer access is required to create a case"})
    data = request_body(event)
    operation = request_headers(event).get("idempotency-key")
    if not operation:
        return response(400, {"message": "idempotency-key header is required"})
    if len(operation) > 128:
        return response(400, {"message": "idempotency-key is too long"})
    required = ("crop", "incidentType", "fieldId")
    if not all(data.get(field) for field in required):
        return response(400, {"message": "crop, incidentType and fieldId are required"})

    idempotency_key = {"PK": f"IDEMPOTENCY#{user_id}", "SK": operation}
    existing = table.get_item(Key=idempotency_key).get("Item")
    if existing:
        return response(200, existing["result"])

    case_id = f"KN-{datetime.now().year % 100:02d}-{uuid.uuid4().hex[:8].upper()}"
    stamp = now()
    item = {
        "PK": f"CASE#{case_id}",
        "SK": "METADATA",
        "GSI1PK": f"USER#{user_id}",
        "GSI1SK": f"CASE#{stamp}",
        "caseId": case_id,
        "userId": user_id,
        "status": "DRAFT",
        "version": 1,
        "createdAt": stamp,
        "updatedAt": stamp,
        "crop": str(data["crop"])[:100],
        "incidentType": str(data["incidentType"])[:100],
        "fieldId": str(data["fieldId"])[:100],
        "occurredAt": data.get("occurredAt"),
        "damageRange": data.get("damageRange"),
    }
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
    result = {"caseId": case_id, "status": "DRAFT", "version": 1, "createdAt": stamp}
    table.put_item(
        Item={
            **idempotency_key,
            "result": result,
            "expiresAt": int(time.time()) + 86400,
        }
    )
    append_event(case_id, "CaseCreated", user_id)
    metrics.add_metric(name="CasesCreated", unit=MetricUnit.Count, value=1)
    return response(201, result)


def list_cases(user_id, groups):
    if has_group(groups, "Reviewers"):
        result = table.query(
            IndexName="GSI2",
            KeyConditionExpression="GSI2PK = :pk",
            ExpressionAttributeValues={":pk": "STATUS#SUBMITTED"},
            ScanIndexForward=False,
        )
    elif has_group(groups, "Farmers"):
        result = table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": f"USER#{user_id}"},
            ScanIndexForward=False,
        )
    else:
        return response(403, {"message": "A farmer or reviewer role is required"})
    return response(200, {"items": result.get("Items", []), "nextToken": None})


def get_case(case_id, user_id, groups):
    case_record = get_case_metadata(case_id)
    if not case_record:
        return response(404, {"message": "Case not found"})
    if not owner_or_reviewer(case_record, user_id, groups):
        return response(403, {"message": "Access denied"})
    result = table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": f"CASE#{case_id}"},
    )
    records = [item for item in result.get("Items", []) if item["SK"] != "METADATA"]
    for record in records:
        if record["SK"].startswith("EVIDENCE#") and record.get("status") in {"PROCESSING_QUEUED", "PROCESSED"}:
            record["downloadUrl"] = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET, "Key": record["objectKey"]},
                ExpiresIn=300,
            )
            record["downloadExpiresIn"] = 300
    return response(200, {"case": case_record, "records": records})


def evidence_url(event, case_id, user_id, groups):
    case_record = get_case_metadata(case_id)
    if not case_record:
        return response(404, {"message": "Case not found"})
    if case_record.get("userId") != user_id or not has_group(groups, "Farmers") or has_group(groups, "Reviewers"):
        return response(403, {"message": "Only the case owner can upload evidence"})
    if case_record.get("status") not in {"DRAFT", "NEEDS_INFORMATION"}:
        return response(409, {"message": "This case is not accepting evidence"})

    data = request_body(event)
    evidence_id = str(data.get("clientEvidenceId") or "")
    kind = str(data.get("kind") or "")
    content_type = str(data.get("contentType") or "")
    sha256 = str(data.get("sha256") or "").lower()
    try:
        size = int(data.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", evidence_id):
        return response(400, {"message": "A valid clientEvidenceId is required"})
    if not kind or content_type not in ALLOWED_TYPES or not re.fullmatch(r"[a-f0-9]{64}", sha256):
        return response(400, {"message": "kind, supported contentType and SHA-256 are required"})
    if size < 1 or size > MAX_EVIDENCE_BYTES:
        return response(400, {"message": "Evidence must be between 1 byte and 20 MB"})

    checksum_sha256 = base64.b64encode(bytes.fromhex(sha256)).decode("ascii")
    key = f"private/{user_id}/{case_id}/{kind}/{evidence_id}.{ALLOWED_TYPES[content_type]}"
    record_key = {"PK": f"CASE#{case_id}", "SK": f"EVIDENCE#{evidence_id}"}
    existing = table.get_item(Key=record_key).get("Item")
    if existing:
        immutable_values_match = (
            existing.get("sha256") == sha256
            and existing.get("contentType") == content_type
            and int(existing.get("size", 0)) == size
        )
        if not immutable_values_match:
            return response(409, {"message": "Evidence identifier already has different metadata"})
        if existing.get("status") in {"PROCESSING_QUEUED", "PROCESSED"}:
            return response(
                200,
                {
                    "evidenceId": evidence_id,
                    "uploadRequired": False,
                    "status": existing["status"],
                    "objectKey": existing["objectKey"],
                },
            )
    else:
        table.put_item(
            Item={
                **record_key,
                "evidenceId": evidence_id,
                "kind": kind[:50],
                "objectKey": key,
                "sha256": sha256,
                "checksumSHA256": checksum_sha256,
                "size": size,
                "contentType": content_type,
                "status": "AWAITING_UPLOAD",
                "capturedAt": data.get("capturedAt"),
                "createdAt": now(),
            },
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
            "ContentType": content_type,
            "ChecksumSHA256": checksum_sha256,
            "Metadata": {"sha256": sha256, "case-id": case_id},
        },
        ExpiresIn=600,
    )
    return response(
        200,
        {
            "evidenceId": evidence_id,
            "uploadUrl": upload_url,
            "uploadRequired": True,
            "expiresIn": 600,
            "objectKey": key,
            "requiredHeaders": {
                "content-type": content_type,
                "x-amz-meta-sha256": sha256,
                "x-amz-meta-case-id": case_id,
                "x-amz-checksum-sha256": checksum_sha256,
            },
        },
    )


def complete_evidence(case_id, evidence_id, user_id, groups):
    case_record = get_case_metadata(case_id)
    if not case_record:
        return response(404, {"message": "Case not found"})
    if case_record.get("userId") != user_id or not has_group(groups, "Farmers") or has_group(groups, "Reviewers"):
        return response(403, {"message": "Only the case owner can confirm evidence"})
    record_key = {"PK": f"CASE#{case_id}", "SK": f"EVIDENCE#{evidence_id}"}
    evidence = table.get_item(Key=record_key).get("Item")
    if not evidence:
        return response(404, {"message": "Evidence upload request not found"})
    if evidence.get("status") in {"PROCESSING_QUEUED", "PROCESSED"}:
        return response(200, {"evidenceId": evidence_id, "status": evidence["status"]})

    try:
        uploaded = s3.head_object(Bucket=BUCKET, Key=evidence["objectKey"], ChecksumMode="ENABLED")
    except ClientError as error:
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status == 404 or error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return response(409, {"message": "The evidence object has not reached secure storage"})
        raise
    metadata = uploaded.get("Metadata", {})
    if metadata.get("sha256") != evidence["sha256"] or metadata.get("case-id") != case_id:
        return response(409, {"message": "Uploaded evidence metadata does not match the request"})
    if int(uploaded.get("ContentLength", -1)) != int(evidence["size"]):
        return response(409, {"message": "Uploaded evidence size does not match the request"})
    expected_checksum = evidence.get("checksumSHA256") or base64.b64encode(bytes.fromhex(evidence["sha256"])).decode("ascii")
    if uploaded.get("ChecksumSHA256") != expected_checksum:
        return response(409, {"message": "S3 SHA-256 checksum does not match the captured file"})

    sqs.send_message(
        QueueUrl=QUEUE,
        MessageBody=json.dumps(
            {
                "type": "PROCESS_EVIDENCE",
                "caseId": case_id,
                "evidenceId": evidence_id,
                "objectKey": evidence["objectKey"],
            }
        ),
    )
    stamp = now()
    table.update_item(
        Key=record_key,
        UpdateExpression="SET #status = :status, uploadedAt = :stamp",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "PROCESSING_QUEUED", ":stamp": stamp},
    )
    append_event(case_id, "EvidenceUploaded", user_id, evidenceId=evidence_id)
    metrics.add_metric(name="EvidenceUploadsConfirmed", unit=MetricUnit.Count, value=1)
    return response(200, {"evidenceId": evidence_id, "status": "PROCESSING_QUEUED"})


def submit_case(case_id, user_id, groups):
    case_record = get_case_metadata(case_id)
    if not case_record:
        return response(404, {"message": "Case not found"})
    if case_record.get("userId") != user_id or not has_group(groups, "Farmers") or has_group(groups, "Reviewers"):
        return response(403, {"message": "Only the case owner can submit this record"})
    if case_record.get("status") == "SUBMITTED":
        return response(200, {"caseId": case_id, "status": "SUBMITTED", "submittedAt": case_record.get("submittedAt")})
    evidence_result = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
        ExpressionAttributeValues={":pk": f"CASE#{case_id}", ":prefix": "EVIDENCE#"},
    )
    evidence = evidence_result.get("Items", [])
    if not evidence or any(item.get("status") not in {"PROCESSING_QUEUED", "PROCESSED"} for item in evidence):
        return response(409, {"message": "All evidence uploads must be confirmed before submission"})
    stamp = now()
    table.update_item(
        Key={"PK": f"CASE#{case_id}", "SK": "METADATA"},
        UpdateExpression="SET #status = :status, submittedAt = :stamp, updatedAt = :stamp, GSI2PK = :queue, GSI2SK = :sort",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "SUBMITTED",
            ":stamp": stamp,
            ":queue": "STATUS#SUBMITTED",
            ":sort": f"SUBMITTED#{stamp}",
        },
    )
    append_event(case_id, "CaseSubmittedForReview", user_id)
    metrics.add_metric(name="CasesSubmitted", unit=MetricUnit.Count, value=1)
    return response(200, {"caseId": case_id, "status": "SUBMITTED", "submittedAt": stamp})


def correction(event, case_id, user_id, groups):
    if not has_group(groups, "Reviewers"):
        return response(403, {"message": "Reviewer role required"})
    case_record = get_case_metadata(case_id)
    if not case_record:
        return response(404, {"message": "Case not found"})
    data = request_body(event)
    message = str(data.get("message") or "").strip()
    if not message:
        return response(400, {"message": "message is required"})
    stamp = now()
    request_id = uuid.uuid4().hex
    table.put_item(
        Item={
            "PK": f"CASE#{case_id}",
            "SK": f"REQUEST#{stamp}#{request_id}",
            "requestId": request_id,
            "message": message[:1000],
            "evidenceKind": data.get("evidenceKind"),
            "status": "OPEN",
            "reviewerId": user_id,
            "createdAt": stamp,
        }
    )
    table.update_item(
        Key={"PK": f"CASE#{case_id}", "SK": "METADATA"},
        UpdateExpression="SET #status = :status, updatedAt = :stamp",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "NEEDS_INFORMATION", ":stamp": stamp},
    )
    append_event(case_id, "CorrectionRequested", user_id, requestId=request_id)
    return response(201, {"requestId": request_id, "status": "OPEN", "createdAt": stamp})


def complete_correction(case_id, request_id, user_id, groups):
    case_record = get_case_metadata(case_id)
    if not case_record:
        return response(404, {"message": "Case not found"})
    if case_record.get("userId") != user_id or not has_group(groups, "Farmers") or has_group(groups, "Reviewers"):
        return response(403, {"message": "Only the case owner can complete this request"})
    result = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
        ExpressionAttributeValues={":pk": f"CASE#{case_id}", ":prefix": "REQUEST#"},
    )
    request_record = next((item for item in result.get("Items", []) if item.get("requestId") == request_id), None)
    if not request_record:
        return response(404, {"message": "Correction request not found"})
    if request_record.get("status") == "FULFILLED":
        return response(200, {"requestId": request_id, "status": "FULFILLED"})
    stamp = now()
    table.update_item(
        Key={"PK": request_record["PK"], "SK": request_record["SK"]},
        UpdateExpression="SET #status = :status, fulfilledAt = :stamp",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "FULFILLED", ":stamp": stamp},
    )
    append_event(case_id, "CorrectionSupplied", user_id, requestId=request_id)
    return response(200, {"requestId": request_id, "status": "FULFILLED", "fulfilledAt": stamp})


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    request_context = event.get("requestContext", {})
    http = request_context.get("http", {})
    method = http.get("method", "GET")
    path = event.get("rawPath") or http.get("path", "")
    logger.append_keys(method=method, path=path)

    if path == "/health":
        return response(200, {"status": "ok", "service": "kisan-nyay-api", "environment": os.getenv("ENVIRONMENT", "dev")})

    user_id, groups = identity(event)
    if not user_id:
        return response(401, {"message": "Authentication required"})
    if path == "/cases" and method == "POST":
        return create_case(event, user_id, groups)
    if path == "/cases" and method == "GET":
        return list_cases(user_id, groups)

    parts = path.strip("/").split("/")
    case_id = parts[1] if len(parts) > 1 and parts[0] == "cases" else None
    if case_id and len(parts) == 2 and method == "GET":
        return get_case(case_id, user_id, groups)
    if case_id and len(parts) == 3 and parts[2] == "evidence-url" and method == "POST":
        return evidence_url(event, case_id, user_id, groups)
    if case_id and len(parts) == 5 and parts[2] == "evidence" and parts[4] == "complete" and method == "POST":
        return complete_evidence(case_id, parts[3], user_id, groups)
    if case_id and len(parts) == 3 and parts[2] == "submit" and method == "POST":
        return submit_case(case_id, user_id, groups)
    if case_id and len(parts) == 3 and parts[2] == "requests" and method == "POST":
        return correction(event, case_id, user_id, groups)
    if case_id and len(parts) == 5 and parts[2] == "requests" and parts[4] == "complete" and method == "POST":
        return complete_correction(case_id, parts[3], user_id, groups)
    return response(404, {"message": "Route not found"})
