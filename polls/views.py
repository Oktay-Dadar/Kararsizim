from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def index(request):
    return render(request, "polls/index.html")


@login_required
def create(request):
    # Placeholder until Faz 3 adds the real form.
    return render(request, "polls/create.html")
