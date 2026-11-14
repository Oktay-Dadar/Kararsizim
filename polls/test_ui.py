import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Poll
from .tests import add_votes, make_poll, make_user

HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")


class StyleRuleTests(SimpleTestCase):
    def test_no_raw_hex_outside_tokens(self):
        css_dir = Path(settings.BASE_DIR) / "static" / "css"
        offenders = {
            path.name: HEX_COLOR.findall(path.read_text(encoding="utf-8"))
            for path in css_dir.glob("*.css")
            if path.name != "tokens.css"
        }
        self.assertEqual({name: hits for name, hits in offenders.items() if hits}, {})

    def test_no_raw_hex_in_templates(self):
        template_dir = Path(settings.BASE_DIR) / "templates"
        offenders = {
            str(path.relative_to(template_dir)): HEX_COLOR.findall(path.read_text(encoding="utf-8"))
            for path in template_dir.rglob("*.html")
        }
        self.assertEqual({name: hits for name, hits in offenders.items() if hits}, {})


class ErrorPageTests(TestCase):
    def test_404_uses_custom_template(self):
        response = self.client.get("/boyle-bir-sayfa-yok/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Aradığın sayfa yok.", status_code=404)

    def test_403_uses_custom_template(self):
        poll = make_poll(make_user())
        self.client.force_login(make_user("baskasi"))
        response = self.client.post(reverse("polls:close", args=[poll.public_id]))
        self.assertContains(response, "Bunu yapma iznin yok.", status_code=403)

    def test_csrf_failure_uses_custom_template(self):
        strict = self.client_class(enforce_csrf_checks=True)
        response = strict.post(reverse("accounts:login"), {"username": "x", "password": "y"})
        self.assertContains(response, "Sayfayı yenileyip tekrar dene.", status_code=403)

    def test_500_renders_without_request_or_database(self):
        with self.assertNumQueries(0):
            html = render_to_string("500.html")
        self.assertIn("Bir şeyler ters gitti.", html)


class MetaTagTests(TestCase):
    def test_poll_page_shares_question(self):
        poll = make_poll(make_user(), question="Kedi mi köpek mi sahiplensem?")
        add_votes(poll, [2, 1])
        response = self.client.get(poll.get_absolute_url())
        self.assertContains(response, '<meta property="og:title" content="Kedi mi köpek mi sahiplensem?">', html=True)
        self.assertContains(response, "3 kişi oy verdi. Sen de oy ver.")
        self.assertContains(response, 'content="http://testserver/static/img/og-image.png"')
        self.assertContains(response, 'name="twitter:card" content="summary_large_image"')

    def test_home_has_default_meta_and_icons(self):
        response = self.client.get(reverse("polls:index"))
        self.assertContains(response, 'property="og:title" content="Kararsızım · Sen sor, kalabalık karar versin."')
        self.assertContains(response, 'rel="icon" href="/static/img/favicon.svg"')
        self.assertContains(response, 'href="#main"')

    def test_question_is_escaped_in_meta(self):
        poll = make_poll(make_user(), question='"><script>alert(1)</script> nedir?')
        response = self.client.get(poll.get_absolute_url())
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertEqual(Poll.objects.count(), 1)


class StaticAssetTests(SimpleTestCase):
    def test_brand_assets_exist(self):
        static = Path(settings.BASE_DIR) / "static"
        for name in ("img/logo.svg", "img/favicon.svg", "img/apple-touch-icon.png", "img/og-image.png", "css/fonts.css"):
            with self.subTest(name=name):
                self.assertTrue((static / name).is_file())
        fonts = list((static / "fonts").glob("*.woff2"))
        self.assertEqual(len(fonts), 12)
        css = (static / "css" / "fonts.css").read_text(encoding="utf-8")
        for font in fonts:
            self.assertIn(font.name, css)
