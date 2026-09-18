import base64
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("TABLE_NAME", "test-table")
os.environ.setdefault("EVIDENCE_BUCKET", "test-bucket")
os.environ.setdefault("PROCESSING_QUEUE_URL", "https://sqs.test/queue")

from functions.api import app  # noqa: E402


class FakeTable:
    def __init__(self, items=None):
        self.items = {(item["PK"], item["SK"]): dict(item) for item in (items or [])}
        self.puts = []
        self.updates = []

    def get_item(self, Key):
        item = self.items.get((Key["PK"], Key["SK"]))
        return {"Item": dict(item)} if item else {}

    def put_item(self, Item, **kwargs):
        key = (Item["PK"], Item["SK"])
        if kwargs.get("ConditionExpression") and key in self.items:
            raise AssertionError("conditional write collided in test")
        self.items[key] = dict(Item)
        self.puts.append(dict(Item))
        return {}

    def update_item(self, Key, **kwargs):
        key = (Key["PK"], Key["SK"])
        item = self.items.setdefault(key, dict(Key))
        values = kwargs.get("ExpressionAttributeValues", {})
        if ":status" in values:
            item["status"] = values[":status"]
        if ":stamp" in values:
            item["updatedAt"] = values[":stamp"]
        self.updates.append((dict(Key), kwargs))
        return {}

    def query(self, **kwargs):
        values = kwargs.get("ExpressionAttributeValues", {})
        pk = values.get(":pk")
        prefix = values.get(":prefix")
        items = [dict(item) for (item_pk, _), item in self.items.items() if item_pk == pk]
        if prefix:
            items = [item for item in items if item["SK"].startswith(prefix)]
        return {"Items": items}


class FakeS3:
    def __init__(self):
        self.presign = None
        self.head = None

    def generate_presigned_url(self, operation, **kwargs):
        self.presign = (operation, kwargs)
        return "https://s3.test/presigned"

    def head_object(self, **kwargs):
        assert self.head is not None
        return self.head


class FakeSqs:
    def __init__(self):
        self.messages = []

    def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return {"MessageId": "message-1"}


def payload(result):
    return json.loads(result["body"])


def case_item(case_id="KN-26-CASE0001", owner="farmer-1", status="DRAFT"):
    return {
        "PK": f"CASE#{case_id}",
        "SK": "METADATA",
        "caseId": case_id,
        "userId": owner,
        "status": status,
    }


@pytest.fixture
def services(monkeypatch):
    table = FakeTable()
    s3 = FakeS3()
    sqs = FakeSqs()
    monkeypatch.setattr(app, "table", table)
    monkeypatch.setattr(app, "s3", s3)
    monkeypatch.setattr(app, "sqs", sqs)
    return table, s3, sqs


def test_case_creation_is_idempotent(services):
    table, _, _ = services
    event = {
        "headers": {"Idempotency-Key": "sync-KN-local-1"},
        "body": json.dumps({"crop": "Paddy", "incidentType": "flood", "fieldId": "F-01"}),
    }

    first = app.create_case(event, "farmer-1", "Farmers")
    second = app.create_case(event, "farmer-1", "Farmers")

    assert first["statusCode"] == 201
    assert second["statusCode"] == 200
    assert payload(first)["caseId"] == payload(second)["caseId"]
    metadata = [item for item in table.puts if item.get("SK") == "METADATA"]
    assert len(metadata) == 1


def test_non_owner_cannot_request_upload_url(services):
    table, s3, _ = services
    case = case_item()
    table.items[(case["PK"], case["SK"])] = case
    event = {
        "body": json.dumps(
            {
                "clientEvidenceId": "evidence-12345678",
                "kind": "wide",
                "contentType": "image/jpeg",
                "sha256": "a" * 64,
                "size": 128,
            }
        )
    }

    result = app.evidence_url(event, case["caseId"], "farmer-2", "Farmers")

    assert result["statusCode"] == 403
    assert s3.presign is None


def test_reviewer_role_is_required_for_correction(services):
    table, _, _ = services
    case = case_item(status="SUBMITTED")
    table.items[(case["PK"], case["SK"])] = case
    event = {"body": json.dumps({"message": "Please add a boundary photograph"})}

    denied = app.correction(event, case["caseId"], "farmer-1", "Farmers")
    allowed = app.correction(event, case["caseId"], "reviewer-1", "[\"Reviewers\"]")

    assert denied["statusCode"] == 403
    assert allowed["statusCode"] == 201
    assert any(item["SK"].startswith("REQUEST#") for item in table.puts)


def test_owner_receives_scoped_presigned_upload(services):
    table, s3, _ = services
    case = case_item()
    table.items[(case["PK"], case["SK"])] = case
    event = {
        "body": json.dumps(
            {
                "clientEvidenceId": "evidence-12345678",
                "kind": "wide",
                "contentType": "image/jpeg",
                "sha256": "b" * 64,
                "size": 2048,
                "capturedAt": "2026-09-18T07:14:00Z",
            }
        )
    }

    result = app.evidence_url(event, case["caseId"], "farmer-1", "Farmers")
    body = payload(result)

    assert result["statusCode"] == 200
    assert body["uploadUrl"] == "https://s3.test/presigned"
    assert body["requiredHeaders"]["x-amz-meta-sha256"] == "b" * 64
    assert body["requiredHeaders"]["x-amz-meta-case-id"] == case["caseId"]
    assert body["requiredHeaders"]["x-amz-checksum-sha256"] == base64.b64encode(bytes.fromhex("b" * 64)).decode("ascii")
    params = s3.presign[1]["Params"]
    assert params["Key"].startswith(f"private/farmer-1/{case['caseId']}/wide/")
    assert params["Metadata"]["sha256"] == "b" * 64
    evidence = table.items[(case["PK"], "EVIDENCE#evidence-12345678")]
    assert evidence["status"] == "AWAITING_UPLOAD"


def test_upload_confirmation_heads_object_and_enqueues_job(services):
    table, s3, sqs = services
    case = case_item()
    evidence = {
        "PK": case["PK"],
        "SK": "EVIDENCE#evidence-12345678",
        "evidenceId": "evidence-12345678",
        "objectKey": "private/farmer-1/case/wide/evidence.jpg",
        "sha256": "c" * 64,
        "size": 512,
        "status": "AWAITING_UPLOAD",
    }
    table.items[(case["PK"], case["SK"])] = case
    table.items[(evidence["PK"], evidence["SK"])] = evidence
    s3.head = {
        "ContentLength": 512,
        "ChecksumSHA256": base64.b64encode(bytes.fromhex("c" * 64)).decode("ascii"),
        "Metadata": {"sha256": "c" * 64, "case-id": case["caseId"]},
    }

    result = app.complete_evidence(case["caseId"], evidence["evidenceId"], "farmer-1", "Farmers")

    assert result["statusCode"] == 200
    assert payload(result)["status"] == "PROCESSING_QUEUED"
    assert len(sqs.messages) == 1
    job = json.loads(sqs.messages[0]["MessageBody"])
    assert job["evidenceId"] == evidence["evidenceId"]
    assert table.items[(evidence["PK"], evidence["SK"])]["status"] == "PROCESSING_QUEUED"
