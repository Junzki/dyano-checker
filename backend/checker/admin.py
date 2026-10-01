import yaml
from django.contrib import admin

from .models import RuleSet, RuleSkillFile, Submission, SubmissionFile
from .schema import parse_ruleset


class SubmissionFileInline(admin.TabularInline):
    model = SubmissionFile
    extra = 0


class RuleSkillFileInline(admin.TabularInline):
    model = RuleSkillFile
    extra = 0


@admin.register(RuleSet)
class RuleSetAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    inlines = [RuleSkillFileInline]

    def save_model(self, request, obj, form, change):
        uploaded = form.cleaned_data.get("yaml_file")
        if uploaded is not None and hasattr(uploaded, "read"):
            uploaded.seek(0)
            data = yaml.safe_load(uploaded.read())
            obj.schema = parse_ruleset(data) if isinstance(data, dict) else {}
        super().save_model(request, obj, form, change)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "rule_set", "status", "created_at")
    list_filter = ("status", "rule_set")
    inlines = [SubmissionFileInline]
