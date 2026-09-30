import json

from asgiref.sync import sync_to_async
from django.http import HttpRequest
from ninja import File, Form, NinjaAPI, Schema
from ninja.files import UploadedFile

from .broker import SubmissionMessage, broker
from .models import RuleSet, Submission, SubmissionFile
from .schema import build_requirement_map

api = NinjaAPI(title="Dyano Checker", version="0.1.0")


class RuleSetOut(Schema):
    id: int
    name: str


class FileRequirementOut(Schema):
    key: str
    name: str
    description: str
    kind: str
    accept: str


class CategoryOut(Schema):
    name: str
    file_requirements: list[FileRequirementOut]


class RuleSetDetailOut(Schema):
    id: int
    name: str
    categories: list[CategoryOut]


class SubmissionOut(Schema):
    id: int
    status: str


class SubmissionFileOut(Schema):
    key: str
    name: str
    original_name: str


class SubmissionDetailOut(Schema):
    id: int
    status: str
    files: list[SubmissionFileOut]


@api.get("/rulesets", response=list[RuleSetOut])
def list_rulesets(request: HttpRequest):
    return [
        {"id": rs.id, "name": rs.name}
        for rs in RuleSet.objects.all().order_by("name")
    ]


@api.get("/rulesets/{rule_set_id}", response=RuleSetDetailOut)
def get_ruleset(request: HttpRequest, rule_set_id: int):
    rs = RuleSet.objects.get(pk=rule_set_id)
    return {
        "id": rs.id,
        "name": rs.name,
        "categories": rs.schema.get("categories", []),
    }


def create_submission_sync(rule_set_id: int, keys: list[str], files: list) -> Submission:
    rule_set = RuleSet.objects.get(pk=rule_set_id)
    requirement_map = build_requirement_map(rule_set.schema)
    submission = Submission.objects.create(rule_set=rule_set)
    for key, uploaded in zip(keys, files):
        meta = requirement_map.get(key, {})
        SubmissionFile.objects.create(
            submission=submission,
            category_name=meta.get("category_name", ""),
            requirement_name=meta.get("requirement_name", key),
            key=key,
            file=uploaded,
            original_name=uploaded.name,
        )
    return submission


@api.post("/submissions", response=SubmissionOut)
async def create_submission(
    request: HttpRequest,
    rule_set_id: Form[int],
    keys_json: Form[str],
    files: File[list[UploadedFile]],
):
    keys_list = json.loads(keys_json)
    submission = await sync_to_async(create_submission_sync)(
        rule_set_id, keys_list, files
    )
    async with broker:
        await broker.publish(
            SubmissionMessage(submission_id=submission.id), channel="submissions"
        )
    return {"id": submission.id, "status": submission.status}


@api.get("/submissions/{submission_id}", response=SubmissionDetailOut)
def get_submission(request: HttpRequest, submission_id: int):
    submission = Submission.objects.prefetch_related("files").get(pk=submission_id)
    return {
        "id": submission.id,
        "status": submission.status,
        "files": [
            {
                "key": f.key,
                "name": f.requirement_name,
                "original_name": f.original_name,
            }
            for f in submission.files.all()
        ],
    }
