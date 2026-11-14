from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import selectors
from .models import Option, Poll

DAILY_POLL_LIMIT = 10
DAILY_POLL_WINDOW = timedelta(hours=24)


def daily_poll_limit_reached(user):
    return selectors.polls_created_since(user, timezone.now() - DAILY_POLL_WINDOW) >= DAILY_POLL_LIMIT


@transaction.atomic
def create_poll(*, author, question, description, options):
    poll = Poll.objects.create(author=author, question=question, description=description)
    Option.objects.bulk_create(
        Option(poll=poll, text=text, position=position) for position, text in enumerate(options)
    )
    return poll
