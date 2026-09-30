import asyncio

from django.core.management.base import BaseCommand

from checker.worker import app


class Command(BaseCommand):
    help = "Run the FastStream Redis worker (status pipeline)."

    def handle(self, *args, **options):
        self.stdout.write("Starting FastStream worker...")
        try:
            asyncio.run(app.run())
        except KeyboardInterrupt:
            self.stdout.write("Worker stopped.")
