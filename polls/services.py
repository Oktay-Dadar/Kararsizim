from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from . import selectors
from .models import Option, Poll, Vote

DAILY_POLL_LIMIT = 10
DAILY_POLL_WINDOW = timedelta(hours=24)


class VoteError(Exception):
    message = "Oy kaydedilemedi."

    def __init__(self, message=None):
        super().__init__(message or self.message)
        self.message = message or self.message


class PollClosed(VoteError):
    message = "Bu anket kapandı."


class InvalidOption(VoteError):
    message = "Geçersiz seçenek."


class AlreadyVoted(VoteError):
    message = "Bu ankete zaten oy verdin."


def daily_poll_limit_reached(user):
    return selectors.polls_created_since(user, timezone.now() - DAILY_POLL_WINDOW) >= DAILY_POLL_LIMIT


@transaction.atomic
def create_poll(*, author, question, description, options):
    poll = Poll.objects.create(author=author, question=question, description=description)
    Option.objects.bulk_create(
        Option(poll=poll, text=text, position=position) for position, text in enumerate(options)
    )
    return poll


def cast_vote(*, poll, option_id, user, voter_key):
    if not poll.is_open:
        raise PollClosed
    if option_id in (None, ""):
        raise InvalidOption("Bir seçenek seç.")
    try:
        option_id = int(option_id)
    except (TypeError, ValueError):
        raise InvalidOption from None
    option = Option.objects.filter(pk=option_id, poll=poll).first()
    if option is None:
        raise InvalidOption

    voter = user if user.is_authenticated else None
    if selectors.has_voted(poll, voter, voter_key):
        raise AlreadyVoted
    try:
        with transaction.atomic():
            Vote.objects.create(poll=poll, option=option, user=voter, voter_key=voter_key)
            Option.objects.filter(pk=option.pk).update(vote_count=F("vote_count") + 1)
            Poll.objects.filter(pk=poll.pk).update(total_votes=F("total_votes") + 1)
    except IntegrityError:
        # A concurrent request from the same person won the race; the DB constraint caught this one.
        raise AlreadyVoted from None
    return option


def close_poll(poll):
    Poll.objects.filter(pk=poll.pk).update(status=Poll.Status.CLOSED)


def delete_poll(poll):
    poll.delete()
