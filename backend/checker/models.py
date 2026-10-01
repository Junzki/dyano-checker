from django.db import models


def submission_upload_path(instance: "SubmissionFile", filename: str) -> str:
    return f"submissions/{instance.submission_id}/{instance.key}/{filename}"


def skill_upload_path(instance: "RuleSkillFile", filename: str) -> str:
    return f"rulesets/{instance.rule_set_id}/skills/{filename}"


def output_template_upload_path(instance: "RuleSet", filename: str) -> str:
    return f"rulesets/{instance.pk}/output-template/{filename}"


class RuleSet(models.Model):
    name = models.CharField(max_length=200, unique=True)
    yaml_file = models.FileField(upload_to="rulesets/")
    output_template = models.FileField(
        upload_to=output_template_upload_path, blank=True
    )
    schema = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class RuleSkillFile(models.Model):
    """A skill/gate/template file uploaded for a specific rule set.

    The rule-set YAML references these files by name (``skill: SKILL1.md``,
    ``gate: GATE1.md``). When a checking task runs, the worker mounts the
    uploaded files into the agent container.
    """

    rule_set = models.ForeignKey(
        RuleSet, related_name="skill_files", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=skill_upload_path)

    class Meta:
        unique_together = ("rule_set", "name")

    def __str__(self) -> str:
        return f"{self.rule_set.name} -> {self.name}"


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
    results = models.JSONField(default=dict, blank=True)
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
