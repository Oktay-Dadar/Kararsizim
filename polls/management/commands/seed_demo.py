import hashlib
import random
from collections import Counter
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from polls.models import Option, Poll, Vote

DEMO_USERS = ["demo_ayse", "demo_mert", "demo_deniz"]

DEMO_POLLS = [
    ("Bugün sinemaya mı gitsem, restorana mı?", ["Sinema", "Restoran"]),
    ("Hafta sonu için hangi şehir?", ["İzmir", "Eskişehir", "Bursa", "Kapadokya"]),
    ("Yeni telefon alırken en önemli özellik ne?", ["Kamera", "Pil ömrü", "Ekran", "Fiyat", "Performans"]),
    ("Sabah kahvesi mi, çay mı?", ["Kahve", "Çay", "İkisi de olmaz"]),
    ("Spor salonuna sabah mı akşam mı gitmeli?", ["Sabah", "Akşam"]),
    ("Doğum günü hediyesi olarak ne alsam?", ["Kitap", "Kulaklık", "Deneyim hediyesi", "Bitki"]),
    ("Yaz tatilinde deniz mi, dağ mı?", ["Deniz", "Dağ", "Evde dinlenmek"]),
    ("İlk evime hangi rengi boyatayım?", ["Beyaz", "Açık gri", "Toprak tonu", "Pastel yeşil"]),
    ("Akşam yemeğinde ne pişireyim?", ["Makarna", "Mercimek çorbası", "Tavuk sote", "Dışarıdan sipariş"]),
    ("Yeni bir dil öğrenecek olsam hangisi?", ["İspanyolca", "Almanca", "Japonca", "İtalyanca", "Korece"]),
    ("Kedi mi sahiplensem köpek mi?", ["Kedi", "Köpek"]),
    ("Bu akşam hangi diziye başlayayım?", ["Bilim kurgu", "Polisiye", "Komedi"]),
]

CLOSED_INDEXES = {3, 7}
EXPIRED_INDEX = 10
EMPTY_INDEX = 11


class Command(BaseCommand):
    help = "Demo veri üretir: 3 kullanıcı, 12 anket, rastgele oylar."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Önceki demo verisini silip yeniden üretir.")
        parser.add_argument("--seed", type=int, default=None, help="Her seferinde aynı veriyi üretmek için.")
        parser.add_argument(
            "--password",
            default=None,
            help="Demo kullanıcılara bu parolayı ata. Verilmezse giriş yapılamaz.",
        )

    @transaction.atomic
    def handle(self, *args, reset, seed, password, **options):
        User = get_user_model()
        existing = User.objects.filter(username__in=DEMO_USERS)
        if existing.exists():
            if not reset:
                raise CommandError("Demo verisi zaten var. Yeniden üretmek için --reset kullan.")
            existing.delete()

        rng = random.Random(seed)
        now = timezone.now()

        users = []
        for username in DEMO_USERS:
            user = User(username=username, email=f"{username}@example.com")
            if password:
                user.set_password(password)
            else:
                user.set_unusable_password()
            users.append(user)
        User.objects.bulk_create(users)
        users = list(User.objects.filter(username__in=DEMO_USERS))

        polls, created_times = [], []
        for index, (question, _) in enumerate(DEMO_POLLS):
            created = now - timedelta(days=rng.uniform(0.2, 14))
            poll = Poll(question=question, author=users[index % len(users)])
            if index in CLOSED_INDEXES:
                poll.status = Poll.Status.CLOSED
            if index == EXPIRED_INDEX:
                poll.closes_at = created + (now - created) / 2
            polls.append(poll)
            created_times.append(created)
        Poll.objects.bulk_create(polls)
        for poll, created in zip(polls, created_times):
            poll.created_at = created
        Poll.objects.bulk_update(polls, ["created_at"])

        options_by_poll = {}
        all_options = []
        for poll, (_, texts) in zip(polls, DEMO_POLLS):
            poll_options = [Option(poll=poll, text=text, position=pos) for pos, text in enumerate(texts)]
            options_by_poll[poll.pk] = poll_options
            all_options.extend(poll_options)
        Option.objects.bulk_create(all_options)

        votes, vote_times = [], []
        for index, poll in enumerate(polls):
            if index == EMPTY_INDEX:
                continue
            poll_options = options_by_poll[poll.pk]
            weights = [rng.uniform(0.5, 3) for _ in poll_options]
            voting_ends = poll.closes_at or now
            span = (voting_ends - poll.created_at).total_seconds()

            def pick_time():
                return poll.created_at + timedelta(seconds=rng.uniform(0, span))

            for user in users:
                if rng.random() < 0.5:
                    votes.append(Vote(poll=poll, option=rng.choices(poll_options, weights)[0], user=user,
                                      voter_key=_demo_key(poll.public_id, user.username)))
                    vote_times.append(pick_time())
            for i in range(rng.randint(3, 60)):
                votes.append(Vote(poll=poll, option=rng.choices(poll_options, weights)[0],
                                  voter_key=_demo_key(poll.public_id, f"anon-{i}")))
                vote_times.append(pick_time())
        Vote.objects.bulk_create(votes)
        for vote, created in zip(votes, vote_times):
            vote.created_at = created
        Vote.objects.bulk_update(votes, ["created_at"], batch_size=200)

        option_counts = Counter(vote.option_id for vote in votes)
        poll_counts = Counter(vote.poll_id for vote in votes)
        for option in all_options:
            option.vote_count = option_counts[option.pk]
        for poll in polls:
            poll.total_votes = poll_counts[poll.pk]
        Option.objects.bulk_update(all_options, ["vote_count"])
        Poll.objects.bulk_update(polls, ["total_votes"])

        login_note = "girişe açık" if password else "giriş yapılamaz"
        self.stdout.write(self.style.SUCCESS(
            f"{len(users)} kullanıcı ({login_note}), {len(polls)} anket, "
            f"{len(all_options)} seçenek, {len(votes)} oy oluşturuldu."
        ))


def _demo_key(public_id, voter):
    return hashlib.sha256(f"demo:{public_id}:{voter}".encode()).hexdigest()
