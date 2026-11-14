from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from . import results, selectors, services
from .forms import PollForm

DAILY_LIMIT_MESSAGE = "24 saatte en fazla 10 anket açabilirsin. Biraz sonra tekrar dene."


def _page_number(request):
    try:
        return max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        return 1


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
            "poll_views": results.build_poll_views(polls, request.user),
            "page": page,
            "has_more": has_more,
        },
    )


def detail(request, public_id):
    poll = selectors.get_poll_or_404(public_id)
    return render(request, "polls/detail.html", {"view": results.build_poll_view(poll, request.user)})


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
            "poll_views": results.build_poll_views(polls, request.user),
            "page": page,
            "has_more": has_more,
        },
    )
