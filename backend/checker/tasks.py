from asgiref.sync import sync_to_async

from .models import Submission


def process_submission_sync(submission_id: int) -> None:
    submission = Submission.objects.get(pk=submission_id)
    submission.status = Submission.Status.PROCESSING
    submission.save(update_fields=["status", "updated_at"])

    for submission_file in submission.files.all():
        if not submission_file.file.storage.exists(submission_file.file.name):
            submission.status = Submission.Status.FAILED
            submission.save(update_fields=["status", "updated_at"])
            return

    submission.status = Submission.Status.COMPLETED
    submission.save(update_fields=["status", "updated_at"])


async def process_submission(submission_id: int) -> None:
    await sync_to_async(process_submission_sync)(submission_id)
