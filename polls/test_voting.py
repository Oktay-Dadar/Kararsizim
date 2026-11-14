from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from . import services
from .models import Poll, Vote
from .tests import PASSWORD, add_votes, make_poll, make_user

JSON = {"HTTP_ACCEPT": "application/json"}


class VoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.voter = make_user("oyveren")

    def setUp(self):
        self.poll = make_poll(self.author, options=("Sinema", "Restoran", "Evde kal"))
        self.options = list(self.poll.options.order_by("position"))

    def vote(self, option_id, client=None, json=True):
        url = reverse("polls:vote", args=[self.poll.public_id])
        return (client or self.client).post(url, {"option": option_id}, **(JSON if json else {}))

    def counts(self):
        self.poll.refresh_from_db()
        return self.poll.total_votes, [o.vote_count for o in self.poll.options.order_by("position")]

    def test_anonymous_vote_increments_counters(self):
        response = self.vote(self.options[1].pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.counts(), (1, [0, 1, 0]))
        data = response.json()
        self.assertEqual(data["voted_option_id"], self.options[1].pk)
        self.assertEqual([o["percent"] for o in data["options"]], [0, 100, 0])
        vote = Vote.objects.get()
        self.assertIsNone(vote.user)
        self.assertEqual(len(vote.voter_key), 64)

    def test_same_session_second_vote_is_409(self):
        self.vote(self.options[0].pk)
        response = self.vote(self.options[2].pk)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["message"], "Bu ankete zaten oy verdin.")
        self.assertEqual(self.counts(), (1, [1, 0, 0]))

    def test_same_user_second_vote_is_409_even_from_another_session(self):
        self.client.force_login(self.voter)
        self.assertEqual(self.vote(self.options[0].pk).status_code, 200)
        other_device = self.client_class()
        other_device.force_login(self.voter)
        self.assertEqual(self.vote(self.options[1].pk, client=other_device).status_code, 409)
        self.assertEqual(self.counts(), (1, [1, 0, 0]))
        self.assertEqual(Vote.objects.get().user, self.voter)

    def test_anonymous_vote_then_login_cannot_vote_again(self):
        self.assertEqual(self.vote(self.options[0].pk).status_code, 200)
        self.client.force_login(self.voter)
        self.assertEqual(self.vote(self.options[1].pk).status_code, 409)
        self.assertEqual(self.counts(), (1, [1, 0, 0]))

    def test_option_from_another_poll_is_400(self):
        other = make_poll(self.author, question="Başka bir anket sorusu")
        response = self.vote(other.options.first().pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.counts(), (0, [0, 0, 0]))

    def test_missing_or_garbage_option_is_400(self):
        missing = self.vote("")
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["message"], "Bir seçenek seç.")
        self.assertEqual(self.vote("abc").status_code, 400)

    def test_closed_poll_vote_is_403(self):
        Poll.objects.filter(pk=self.poll.pk).update(status=Poll.Status.CLOSED)
        self.assertEqual(self.vote(self.options[0].pk).status_code, 403)
        Poll.objects.filter(pk=self.poll.pk).update(
            status=Poll.Status.ACTIVE, closes_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertEqual(self.vote(self.options[0].pk).status_code, 403)
        self.assertEqual(self.counts(), (0, [0, 0, 0]))

    def test_author_can_vote_on_own_poll(self):
        self.client.force_login(self.author)
        self.assertEqual(self.vote(self.options[0].pk).status_code, 200)

    def test_without_js_vote_redirects_with_message(self):
        response = self.vote(self.options[0].pk, json=False)
        self.assertRedirects(response, self.poll.get_absolute_url(), fetch_redirect_response=False)
        page = self.client.get(self.poll.get_absolute_url())
        self.assertContains(page, "Oyun kaydedildi.")
        self.assertContains(page, "option-row--voted")
        self.assertContains(page, '<span class="option-row__percent">%100</span>', html=True)
        self.assertNotContains(page, "data-vote-form")
        again = self.vote(self.options[1].pk, json=False)
        self.assertRedirects(again, self.poll.get_absolute_url(), fetch_redirect_response=False)
        self.assertContains(self.client.get(self.poll.get_absolute_url()), "Bu ankete zaten oy verdin.")

    def test_x_requested_with_gets_json(self):
        url = reverse("polls:vote", args=[self.poll.public_id])
        response = self.client.post(url, {"option": self.options[0].pk}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response["Content-Type"], "application/json")

    def test_vote_requires_post(self):
        self.assertEqual(self.client.get(reverse("polls:vote", args=[self.poll.public_id])).status_code, 405)

    def test_vote_requires_csrf_token(self):
        strict = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(self.vote(self.options[0].pk, client=strict).status_code, 403)
        self.assertEqual(self.counts(), (0, [0, 0, 0]))

    def test_detail_shows_vote_form_then_results(self):
        page = self.client.get(self.poll.get_absolute_url())
        self.assertContains(page, "data-vote-form")
        self.assertContains(page, 'type="radio"', count=3)
        self.vote(self.options[0].pk)
        page = self.client.get(self.poll.get_absolute_url())
        self.assertNotContains(page, "data-vote-form")
        self.assertNotContains(page, "Yüzdeler oy verdikten sonra görünür.")

    def test_closed_poll_shows_disabled_vote_controls(self):
        Poll.objects.filter(pk=self.poll.pk).update(status=Poll.Status.CLOSED)
        page = self.client.get(self.poll.get_absolute_url())
        self.assertNotContains(page, "data-vote-form")
        self.assertContains(page, "vote-form__closed")
        self.assertContains(page, " disabled", count=4)
        self.assertContains(page, "Bu anket kapandı.")

    def test_feed_card_shows_real_bar_after_voting(self):
        add_votes(self.poll, [2, 1, 0])
        self.assertContains(self.client.get(reverse("polls:index")), "Oy ver, kalabalığı gör")
        self.vote(self.options[0].pk)
        feed = self.client.get(reverse("polls:index"))
        self.assertNotContains(feed, "Oy ver, kalabalığı gör")
        self.assertContains(feed, "Sinema %75")


class ResultsJsonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user("sahip", "sahip.gizli@example.com", PASSWORD)

    def results(self, poll):
        return self.client.get(reverse("polls:results", args=[poll.public_id])).json()

    def test_counts_hidden_before_voting(self):
        poll = make_poll(self.author)
        add_votes(poll, [2, 1])
        data = self.results(poll)
        self.assertEqual(data["total"], 3)
        self.assertTrue(all(o["count"] is None and o["percent"] is None for o in data["options"]))
        self.assertIsNone(data["voted_option_id"])
        self.assertTrue(data["is_open"])

    def test_percentages_sum_to_100_with_3_and_7_votes(self):
        for counts in ([1, 1, 1], [2, 2, 3], [1, 3, 3], [3, 4]):
            with self.subTest(counts=counts):
                options = [f"Seçenek {i}" for i in range(len(counts))]
                poll = make_poll(self.author, question=f"Yuvarlama sorusu {counts}", options=options)
                add_votes(poll, counts)
                Poll.objects.filter(pk=poll.pk).update(status=Poll.Status.CLOSED)
                data = self.results(poll)
                self.assertEqual(sum(o["percent"] for o in data["options"]), 100)

    def test_no_email_or_user_id_leaks(self):
        poll = make_poll(self.author)
        add_votes(poll, [1, 1])
        self.client.force_login(self.author)
        response = self.client.get(reverse("polls:results", args=[poll.public_id]))
        body = response.content.decode()
        for forbidden in ("sahip.gizli", "email", "user", "author"):
            self.assertNotIn(forbidden, body)
        self.assertEqual(
            set(response.json()), {"total", "options", "voted_option_id", "is_open", "results_visible", "badge"}
        )
        self.assertEqual(set(response.json()["options"][0]), {"id", "text", "position", "count", "percent"})


class CloseDeleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.stranger = make_user("yabanci")

    def setUp(self):
        self.poll = make_poll(self.author)

    def test_owner_closes_after_confirmation(self):
        self.client.force_login(self.author)
        url = reverse("polls:close", args=[self.poll.public_id])
        self.assertContains(self.client.get(url), "yeniden açılamaz")
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.status, Poll.Status.ACTIVE)
        response = self.client.post(url, follow=True)
        self.assertRedirects(response, self.poll.get_absolute_url())
        self.assertContains(response, "Anket kapatıldı.")
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.status, Poll.Status.CLOSED)

    def test_owner_deletes_after_confirmation(self):
        self.client.force_login(self.author)
        url = reverse("polls:delete", args=[self.poll.public_id])
        self.assertContains(self.client.get(url), "geri alınamaz")
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())
        response = self.client.post(url, follow=True)
        self.assertRedirects(response, reverse("polls:profile", args=[self.author.username]))
        self.assertContains(response, "Anket silindi.")
        self.assertFalse(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_strangers_get_403(self):
        self.client.force_login(self.stranger)
        for name in ("polls:close", "polls:delete"):
            with self.subTest(name=name):
                url = reverse(name, args=[self.poll.public_id])
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url).status_code, 403)
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.status, Poll.Status.ACTIVE)

    def test_anonymous_is_sent_to_login(self):
        response = self.client.post(reverse("polls:delete", args=[self.poll.public_id]))
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_owner_actions_only_visible_to_owner(self):
        close_url = reverse("polls:close", args=[self.poll.public_id])
        self.assertNotContains(self.client.get(self.poll.get_absolute_url()), close_url)
        self.client.force_login(self.author)
        self.assertContains(self.client.get(self.poll.get_absolute_url()), close_url)


class VotedFeedQueryCountTests(TestCase):
    def test_query_count_constant_for_voter(self):
        author = make_user()
        voter = make_user("sayac")
        self.client.force_login(voter)

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(reverse("polls:index"))
            return len(ctx.captured_queries)

        def add_and_vote(n):
            for _ in range(n):
                poll = make_poll(author, question=f"Oy sayaç sorusu {Poll.objects.count()}")
                services.cast_vote(poll=poll, option_id=poll.options.first().pk, user=voter, voter_key="k" * 64)

        add_and_vote(2)
        few = count_queries()
        add_and_vote(12)
        self.assertEqual(count_queries(), few)
