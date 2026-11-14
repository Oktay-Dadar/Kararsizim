from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Poll, Vote

PAGE_SIZE = 20
POPULAR_WINDOW = timedelta(days=7)

FEED_TABS = {
    "yeni": "Yeni",
    "populer": "Popüler",
    "kapananlar": "Kapananlar",
}
DEFAULT_TAB = "yeni"


def open_q(now):
    return Q(status=Poll.Status.ACTIVE) & (Q(closes_at__isnull=True) | Q(closes_at__gt=now))


def _with_card_data(queryset):
    return queryset.select_related("author").prefetch_related("options")


def _page(queryset, page):
    """Fetch one extra row to know whether a next page exists without a COUNT query."""
    start = (page - 1) * PAGE_SIZE
    rows = list(queryset[start : start + PAGE_SIZE + 1])
    return rows[:PAGE_SIZE], len(rows) > PAGE_SIZE


def feed(tab, page=1):
    now = timezone.now()
    polls = _with_card_data(Poll.objects.all())
    if tab == "populer":
        polls = (
            polls.filter(open_q(now))
            .annotate(recent_votes=Count("votes", filter=Q(votes__created_at__gte=now - POPULAR_WINDOW)))
            .filter(recent_votes__gt=0)
            .order_by("-recent_votes", "-created_at")
        )
    elif tab == "kapananlar":
        polls = polls.exclude(open_q(now)).order_by("-created_at")
    else:
        polls = polls.filter(open_q(now)).order_by("-created_at")
    return _page(polls, page)


def get_poll_or_404(public_id):
    return get_object_or_404(_with_card_data(Poll.objects.all()), public_id=public_id)


def _voter_q(user, voter_key):
    """Votes cast by this account, or from this browser session (even before logging in)."""
    condition = Q()
    if user is not None and user.is_authenticated:
        condition |= Q(user=user)
    if voter_key:
        condition |= Q(voter_key=voter_key)
    return condition


def has_voted(poll, user, voter_key):
    condition = _voter_q(user, voter_key)
    return bool(condition) and Vote.objects.filter(condition, poll=poll).exists()


def voted_options(polls, user, voter_key):
    """{poll_id: option_id} for the given polls, in a single query."""
    poll_ids = [poll.pk for poll in polls]
    condition = _voter_q(user, voter_key)
    if not poll_ids or not condition:
        return {}
    return dict(Vote.objects.filter(condition, poll_id__in=poll_ids).values_list("poll_id", "option_id"))


def polls_created_since(user, since):
    return Poll.objects.filter(author=user, created_at__gte=since).count()


def get_user_or_404(username):
    return get_object_or_404(get_user_model(), username__iexact=username, is_active=True)


def user_polls(user, page=1):
    return _page(_with_card_data(Poll.objects.filter(author=user)).order_by("-created_at"), page)


def user_stats(user):
    stats = Poll.objects.filter(author=user).aggregate(poll_count=Count("id"), vote_count=Sum("total_votes"))
    return {"poll_count": stats["poll_count"], "vote_count": stats["vote_count"] or 0}
