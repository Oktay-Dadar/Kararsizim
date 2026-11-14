from django.test import SimpleTestCase

from config.settings import vercel_hosts


class VercelHostsTests(SimpleTestCase):
    def test_collects_vercel_hosts_without_duplicates(self):
        environ = {
            "VERCEL_PROJECT_PRODUCTION_URL": "kararsizim.vercel.app",
            "VERCEL_BRANCH_URL": "kararsizim-git-main-team.vercel.app",
            "VERCEL_URL": "Kararsizim.vercel.app",
        }
        self.assertEqual(
            vercel_hosts(environ),
            ["kararsizim.vercel.app", "kararsizim-git-main-team.vercel.app"],
        )

    def test_empty_outside_vercel(self):
        self.assertEqual(vercel_hosts({"VERCEL_URL": "  "}), [])
