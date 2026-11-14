from dataclasses import dataclass
from fractions import Fraction

BADGE_FIRST_VOTE = "İlk oyu sen ver"
BADGE_CLOSED_EMPTY = "Oy verilmeden kapandı"
BADGE_HIDDEN = "Oy ver, kalabalığı gör"
BADGE_SPLIT = "Kalabalık da kararsız"
BADGE_CLOSE = "Az farkla önde"
BADGE_CLEAR = "Karar net"


@dataclass(frozen=True)
class Segment:
    position: int
    weight: int


@dataclass(frozen=True)
class OptionResult:
    id: int
    text: str
    position: int
    count: int | None
    percent: int | None


@dataclass(frozen=True)
class PollView:
    poll: object
    results_visible: bool
    real_bar: bool
    segments: list
    options: list
    badge_text: str
    badge_kind: str
    bar_label: str


def percentages(counts):
    """Half-up rounded percentages; any rounding drift is absorbed by the largest option."""
    total = sum(counts)
    if total == 0:
        return [0] * len(counts)
    rounded = [int(Fraction(count * 100, total) + Fraction(1, 2)) for count in counts]
    drift = 100 - sum(rounded)
    if drift:
        largest = max(range(len(counts)), key=lambda index: counts[index])
        rounded[largest] += drift
    return rounded


def badge_for(percents):
    top, runner_up = sorted(percents, reverse=True)[:2]
    gap = top - runner_up
    if gap <= 5:
        return BADGE_SPLIT, "split"
    if gap <= 20:
        return BADGE_CLOSE, "close"
    return BADGE_CLEAR, "clear"


def can_see_results(poll, viewer, voted_poll_ids=frozenset()):
    if not poll.is_open:
        return True
    if getattr(viewer, "is_authenticated", False) and viewer.pk == poll.author_id:
        return True
    return poll.pk in voted_poll_ids


def build_poll_view(poll, viewer, voted_poll_ids=frozenset()):
    options = list(poll.options.all())
    counts = [option.vote_count for option in options]
    total = sum(counts)
    visible = can_see_results(poll, viewer, voted_poll_ids)
    percents = percentages(counts)

    if total and visible:
        segments = [Segment(o.position, o.vote_count) for o in options]
        badge_text, badge_kind = badge_for(percents)
        bar_label = ", ".join(f"{o.text} %{p}" for o, p in zip(options, percents))
    else:
        segments = [Segment(o.position, 1) for o in options]
        if total:
            badge_text, badge_kind = BADGE_HIDDEN, "hidden"
            bar_label = "Sonuçlar oy verdikten sonra görünür."
        else:
            badge_text, badge_kind = (BADGE_FIRST_VOTE, "empty") if poll.is_open else (BADGE_CLOSED_EMPTY, "empty")
            bar_label = "Henüz oy yok."

    option_results = [
        OptionResult(
            id=o.pk,
            text=o.text,
            position=o.position,
            count=o.vote_count if visible else None,
            percent=p if visible else None,
        )
        for o, p in zip(options, percents)
    ]
    return PollView(
        poll=poll,
        results_visible=visible,
        real_bar=bool(total and visible),
        segments=segments,
        options=option_results,
        badge_text=badge_text,
        badge_kind=badge_kind,
        bar_label=bar_label,
    )


def build_poll_views(polls, viewer, voted_poll_ids=frozenset()):
    return [build_poll_view(poll, viewer, voted_poll_ids) for poll in polls]
