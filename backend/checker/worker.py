import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from faststream import FastStream  # noqa: E402

from .broker import SubmissionMessage, broker  # noqa: E402
from .tasks import process_submission  # noqa: E402

app = FastStream(broker)


@broker.subscriber("submissions")
async def on_submission(message: SubmissionMessage) -> None:
    await process_submission(message.submission_id)
