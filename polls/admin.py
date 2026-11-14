from django.contrib import admin

from .models import Option, Poll, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0
    max_num = 5
    fields = ("position", "text", "vote_count")
    readonly_fields = ("vote_count",)


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "status", "total_votes", "created_at")
    list_filter = ("status",)
    search_fields = ("question", "public_id", "author__username")
    list_select_related = ("author",)
    autocomplete_fields = ("author",)
    readonly_fields = ("public_id", "total_votes", "created_at")
    inlines = [OptionInline]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("poll", "option", "user", "created_at")
    list_select_related = ("poll", "option", "user")
    search_fields = ("poll__public_id", "poll__question")

    # Oylar yalnızca uygulama üzerinden eklenir; adminden eklemek sayaçları bozar.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
