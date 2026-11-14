from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import results, selectors, services
from .forms import PollForm
from .utils import get_voter_key

DAILY_LIMIT_MESSAGE = "24 saatte en fazla 10 anket açabilirsin. Biraz sonra tekrar dene."

VOTE_ERROR_STATUS = {
    services.PollClosed: 403,
    services.InvalidOption: 400,
    services.AlreadyVoted: 409,
}


def _page_number(request):
    try:
        return max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        return 1


def _wants_json(request):
    return (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def _poll_views(request, polls):
    voted = selectors.voted_options(polls, request.user, get_voter_key(request))
    return results.build_poll_views(polls, request.user, voted)


def _poll_view(request, poll, voter_key=None):
    voted = selectors.voted_options([poll], request.user, voter_key or get_voter_key(request))
    return results.build_poll_view(poll, request.user, voted)


def _owned_poll_or_403(request, public_id):
    poll = selectors.get_poll_or_404(public_id)
    if poll.author_id != request.user.pk:
        raise PermissionDenied
    return poll


def index(request):
    tab = request.GET.get("sekme", selectors.DEFAULT_TAB)
    if tab not in selectors.FEED_TABS:
        tab = selectors.DEFAULT_TAB
    page = _page_number(request)
    polls, has_more = selectors.feed(tab, page)
    return render(
        request,
        "polls/index.html",
        {
            "tab": tab,
            "tabs": selectors.FEED_TABS.items(),
            "poll_views": _poll_views(request, polls),
            "page": page,
            "has_more": has_more,
        },
    )


def detail(request, public_id):
    poll = selectors.get_poll_or_404(public_id)
    return render(request, "polls/detail.html", {"view": _poll_view(request, poll)})


@require_POST
def vote(request, public_id):
    poll = selectors.get_poll_or_404(public_id)
    voter_key = get_voter_key(request, create=True)
    status, level, message = 200, messages.SUCCESS, "Oyun kaydedildi."
    try:
        services.cast_vote(poll=poll, option_id=request.POST.get("option"), user=request.user, voter_key=voter_key)
    except services.VoteError as error:
        status, level, message = VOTE_ERROR_STATUS[type(error)], messages.ERROR, error.message

    if _wants_json(request):
        fresh = selectors.get_poll_or_404(public_id)
        payload = results.results_payload(_poll_view(request, fresh, voter_key))
        return JsonResponse({**payload, "message": message}, status=status)
    messages.add_message(request, level, message)
    return redirect(poll)


@never_cache
@require_GET
def results_json(request, public_id):
    poll = selectors.get_poll_or_404(public_id)
    return JsonResponse(results.results_payload(_poll_view(request, poll)))


@login_required
def create(request):
    form = PollForm(request.POST or None)
    limit_reached = services.daily_poll_limit_reached(request.user)
    if request.method == "POST" and form.is_valid():
        if limit_reached:
            form.add_error(None, DAILY_LIMIT_MESSAGE)
        else:
            poll = services.create_poll(author=request.user, **form.cleaned_data)
            messages.success(request, "Anketin yayında.")
            return redirect(poll)
    return render(request, "polls/create.html", {"form": form, "limit_reached": limit_reached})


@login_required
def close(request, public_id):
    poll = _owned_poll_or_403(request, public_id)
    if not poll.is_open:
        messages.info(request, "Bu anket zaten kapalı.")
        return redirect(poll)
    if request.method == "POST":
        services.close_poll(poll)
        messages.success(request, "Anket kapatıldı.")
        return redirect(poll)
    return render(
        request,
        "polls/confirm.html",
        {
            "poll": poll,
            "title": "Anketi kapat",
            "message": "Kapatılan ankete artık oy verilemez ve anket yeniden açılamaz. Sonuçlar herkese görünür.",
            "confirm_label": "Anketi kapat",
            "confirm_class": "btn-primary",
        },
    )


@login_required
def delete(request, public_id):
    poll = _owned_poll_or_403(request, public_id)
    if request.method == "POST":
        services.delete_poll(poll)
        messages.success(request, "Anket silindi.")
        return redirect("polls:profile", username=request.user.username)
    return render(
        request,
        "polls/confirm.html",
        {
            "poll": poll,
            "title": "Anketi sil",
            "message": "Anket ve tüm oyları silinir. Bu işlem geri alınamaz.",
            "confirm_label": "Anketi sil",
            "confirm_class": "btn-danger",
        },
    )


def profile(request, username):
    profile_user = selectors.get_user_or_404(username)
    if profile_user.username != username:
        return redirect("polls:profile", username=profile_user.username, permanent=True)
    page = _page_number(request)
    polls, has_more = selectors.user_polls(profile_user, page)
    return render(
        request,
        "polls/profile.html",
        {
            "profile_user": profile_user,
            "stats": selectors.user_stats(profile_user),
            "poll_views": _poll_views(request, polls),
            "page": page,
            "has_more": has_more,
        },
    )
