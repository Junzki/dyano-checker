from django.db import models


def submission_upload_path(instance: "SubmissionFile", filename: str) -> str:
    return f"submissions/{instance.submission_id}/{instance.key}/{filename}"


class RuleSet(models.Model):
    name = models.CharField(max_length=200, unique=True)
    yaml_file = models.FileField(upload_to="rulesets/")
    schema = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Submission(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    rule_set = models.ForeignKey(
        RuleSet, related_name="submissions", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Submission #{self.id} ({self.rule_set.name})"


class SubmissionFile(models.Model):
    submission = models.ForeignKey(
        Submission, related_name="files", on_delete=models.CASCADE
    )
    category_name = models.CharField(max_length=200)
    requirement_name = models.CharField(max_length=200)
    key = models.CharField(max_length=50)
    file = models.FileField(upload_to=submission_upload_path)
    original_name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"{self.requirement_name} -> {self.original_name}"
