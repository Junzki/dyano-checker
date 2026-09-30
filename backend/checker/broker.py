from django.conf import settings
from faststream.redis import RedisBroker
from pydantic import BaseModel

broker = RedisBroker(settings.REDIS_URL)


class SubmissionMessage(BaseModel):
    submission_id: int
