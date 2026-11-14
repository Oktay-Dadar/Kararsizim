from datetime import timedelta

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from . import results, selectors, services
from .models import Poll, Vote

PASSWORD = "kararsiz-test-parola-1"


def make_user(username="yazar"):
    return User.objects.create_user(username, f"{username}@example.com", PASSWORD)


def make_poll(author, question="Bugün ne yapsam acaba?", options=("Sinema", "Restoran"), **fields):
    poll = services.create_poll(author=author, question=question, description="", options=list(options))
    if fields:
        Poll.objects.filter(pk=poll.pk).update(**fields)
        poll.refresh_from_db()
    return poll


def add_votes(poll, counts, created_at=None):
    """counts[i] anonymous votes for option at position i."""
    options = list(poll.options.order_by("position"))
    votes = []
    for option, count in zip(options, counts):
        for i in range(count):
            votes.append(Vote(poll=poll, option=option, voter_key=f"{poll.pk}-{option.pk}-{i}-{created_at}"))
    Vote.objects.bulk_create(votes)
    if created_at:
        Vote.objects.filter(pk__in=[v.pk for v in votes]).update(created_at=created_at)
    for option, count in zip(options, counts):
        option.vote_count += count
        option.save(update_fields=["vote_count"])
    poll.total_votes += sum(counts)
    poll.save(update_fields=["total_votes"])


class PercentageTests(SimpleTestCase):
    def test_percentages_always_sum_to_100(self):
        for counts in ([1, 1, 1], [1, 2, 4], [3, 3, 1], [1, 1, 1, 1, 3], [2, 1], [1, 6], [7, 0, 0]):
            with self.subTest(counts=counts):
                self.assertEqual(sum(results.percentages(counts)), 100)

    def test_rounding_drift_goes_to_largest_option(self):
        self.assertEqual(results.percentages([1, 1, 1]), [34, 33, 33])
        self.assertEqual(results.percentages([1, 2, 4]), [14, 29, 57])

    def test_zero_votes(self):
        self.assertEqual(results.percentages([0, 0]), [0, 0])

    def test_badges(self):
        self.assertEqual(results.badge_for([50, 50])[0], "Kalabalık da kararsız")
        self.assertEqual(results.badge_for([53, 47])[0], "Az farkla önde")
        self.assertEqual(results.badge_for([60, 40])[0], "Az farkla önde")
        self.assertEqual(results.badge_for([61, 39])[0], "Karar net")


class CreatePollTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def setUp(self):
        self.client.force_login(self.user)

    def post(self, options, question="Hafta sonu nereye gitsem?"):
        return self.client.post(reverse("polls:create"), {"question": question, "description": "", "options": options})

    def test_anonymous_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("polls:create"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_one_option_is_rejected(self):
        response = self.post(["Sadece bu", "", "", "", ""])
        self.assertContains(response, "En az 2 seçenek gerekli.")
        self.assertFalse(Poll.objects.exists())

    def test_six_options_are_rejected(self):
        response = self.post(["A1", "B2", "C3", "D4", "E5", "F6"])
        self.assertContains(response, "En fazla 5 seçenek ekleyebilirsin.")
        self.assertFalse(Poll.objects.exists())

    def test_duplicate_options_are_rejected(self):
        response = self.post(["Elma", " elma ", "", "", ""])
        self.assertContains(response, "seçeneğini iki kez yazdın.")
        self.assertFalse(Poll.objects.exists())

    def test_blank_rows_are_ignored_and_positions_are_compact(self):
        response = self.post(["İzmir", "", "Bursa", "", "Eskişehir"])
        poll = Poll.objects.get()
        self.assertRedirects(response, poll.get_absolute_url())
        self.assertEqual(list(poll.options.values_list("position", "text")),
                         [(0, "İzmir"), (1, "Bursa"), (2, "Eskişehir")])
        self.assertEqual(len(poll.public_id), 12)

    def test_short_question_is_rejected(self):
        response = self.post(["A", "B"], question="Kısa?")
        self.assertContains(response, "Soru en az 10 karakter olmalı.")

    def test_daily_limit_counts_last_24_hours(self):
        for i in range(services.DAILY_POLL_LIMIT):
            make_poll(self.user, question=f"Eski soru numara {i}")
        Poll.objects.filter(pk=Poll.objects.first().pk).update(created_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(self.post(["A", "B"]).status_code, 302)
        response = self.post(["A", "B"])
        self.assertContains(response, "24 saatte en fazla 10 anket açabilirsin.")
        self.assertEqual(Poll.objects.count(), services.DAILY_POLL_LIMIT + 1)


class FeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()

    def test_tabs_split_open_and_closed_polls(self):
        open_poll = make_poll(self.author, question="Açık anket sorusu")
        closed = make_poll(self.author, question="Kapatılmış anket sorusu", status=Poll.Status.CLOSED)
        expired = make_poll(self.author, question="Süresi dolmuş anket", closes_at=timezone.now() - timedelta(hours=1))
        new_tab = self.client.get(reverse("polls:index"))
        closed_tab = self.client.get(reverse("polls:index"), {"sekme": "kapananlar"})
        self.assertContains(new_tab, open_poll.question)
        self.assertNotContains(new_tab, closed.question)
        self.assertNotContains(new_tab, expired.question)
        self.assertContains(closed_tab, closed.question)
        self.assertContains(closed_tab, expired.question)
        self.assertNotContains(closed_tab, open_poll.question)

    def test_popular_orders_by_last_7_days_votes(self):
        recent_three = make_poll(self.author, question="Üç yeni oylu anket")
        recent_one = make_poll(self.author, question="Bir yeni oylu anket")
        old_five = make_poll(self.author, question="Beş eski oylu anket")
        add_votes(recent_three, [2, 1])
        add_votes(recent_one, [1, 0])
        add_votes(old_five, [3, 2], created_at=timezone.now() - timedelta(days=10))
        polls, _ = selectors.feed("populer")
        self.assertEqual([p.pk for p in polls], [recent_three.pk, recent_one.pk])

    def test_pagination_shows_20_and_load_more(self):
        for i in range(25):
            make_poll(self.author, question=f"Sayfalama sorusu {i:02d}")
        first = self.client.get(reverse("polls:index"))
        self.assertEqual(len(first.context["poll_views"]), 20)
        self.assertContains(first, "Daha fazla göster")
        second = self.client.get(reverse("polls:index"), {"page": 2})
        self.assertEqual(len(second.context["poll_views"]), 5)
        self.assertNotContains(second, "Daha fazla göster")

    def test_query_count_does_not_grow_with_polls(self):
        user = make_user("okuyucu")
        self.client.force_login(user)

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(reverse("polls:index")).status_code, 200)
            return len(ctx.captured_queries)

        for i in range(3):
            add_votes(make_poll(self.author, question=f"Az anket sorusu {i}"), [1, 1])
        few = count_queries()
        for i in range(17):
            add_votes(make_poll(self.author, question=f"Çok anket sorusu {i}"), [2, 1])
        self.assertEqual(count_queries(), few)

    def test_empty_state(self):
        self.assertContains(self.client.get(reverse("polls:index")), "İlk kararsızlığını sen paylaş.")


class ResultVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.poll = make_poll(cls.author, options=("Sinema", "Restoran", "Evde kal"))
        add_votes(cls.poll, [3, 2, 1])

    def test_percentages_hidden_from_non_voters_on_open_poll(self):
        response = self.client.get(self.poll.get_absolute_url())
        self.assertNotContains(response, "option-row__percent")
        self.assertContains(response, "Oy ver, kalabalığı gör")
        self.assertContains(response, "<span class=\"num\">6</span> kişi oy verdi")
        feed = self.client.get(reverse("polls:index"))
        self.assertNotContains(feed, "Sinema %")

    def test_owner_sees_percentages(self):
        self.client.force_login(self.author)
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, '<span class="option-row__percent">%50</span>', html=True)
        self.assertContains(response, "Az farkla önde")

    def test_closed_poll_shows_percentages(self):
        Poll.objects.filter(pk=self.poll.pk).update(status=Poll.Status.CLOSED)
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, '<span class="option-row__percent">%17</span>', html=True)

    def test_closed_poll_without_votes_badge(self):
        empty = make_poll(self.author, question="Oysuz kapanmış anket", status=Poll.Status.CLOSED)
        self.assertContains(self.client.get(empty.get_absolute_url()), "Oy verilmeden kapandı")

    def test_unknown_poll_is_404(self):
        self.assertEqual(self.client.get(reverse("polls:detail", args=["yokboylebir1"])).status_code, 404)


class ProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("KararVer", "gizli.profil@example.com", PASSWORD)
        add_votes(make_poll(cls.user, question="Profil anketi bir"), [2, 1])
        make_poll(cls.user, question="Profil anketi iki")

    def test_profile_shows_polls_and_stats_without_email(self):
        response = self.client.get(reverse("polls:profile", args=["KararVer"]))
        self.assertContains(response, "Profil anketi bir")
        self.assertContains(response, "Profil anketi iki")
        self.assertEqual(response.context["stats"], {"poll_count": 2, "vote_count": 3})
        self.assertNotContains(response, "gizli.profil")

    def test_profile_redirects_to_canonical_case(self):
        response = self.client.get(reverse("polls:profile", args=["kararver"]))
        self.assertRedirects(response, reverse("polls:profile", args=["KararVer"]), status_code=301)

    def test_unknown_profile_is_404(self):
        self.assertEqual(self.client.get(reverse("polls:profile", args=["kimseyok"])).status_code, 404)

    def test_poll_pages_never_render_author_email(self):
        poll = Poll.objects.first()
        self.assertNotContains(self.client.get(poll.get_absolute_url()), "gizli.profil")
        self.assertNotContains(self.client.get(reverse("polls:index")), "gizli.profil")
