"""Access-control tests for the staff-only /manage section.

The point of these is the middle row of the matrix: a logged-in **non-staff**
user. Before the custom user model there was no such account, so
``login_required`` and "is an administrator" were accidentally the same thing.
They are not, and these tests are what keeps them apart once regular user
accounts exist.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from players.models import Player

User = get_user_model()

# Every URL under /manage. A new one added without a gate fails
# test_all_manage_urls_are_covered rather than quietly shipping open.
MANAGE_URL_NAMES = [
    "manage_redirect",
    "manage_players",
    "manage_player_add",
    "manage_import",
    "manage_roster",
    "manage_roster_download",
    "manage_roster_download_csv",
]


class ManageAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.player = Player.objects.create(player_number="1", name="Ada Lovelace")
        cls.staff = User.objects.create_user(
            username="admin", password="pw-admin-1234", is_staff=True
        )
        cls.regular = User.objects.create_user(
            username="ada", password="pw-ada-1234", player=cls.player
        )
        cls.inactive_staff = User.objects.create_user(
            username="former", password="pw-former-1234", is_staff=True, is_active=False
        )

    def manage_urls(self):
        urls = [reverse(name) for name in MANAGE_URL_NAMES]
        urls.append(reverse("manage_player_edit", args=[self.player.pk]))
        return urls

    def test_anonymous_is_redirected_to_login(self):
        for url in self.manage_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("manage_login"), response["Location"])
                # The destination is preserved so login lands where they meant.
                self.assertIn(url, response["Location"])

    def test_regular_user_is_forbidden(self):
        """A logged-in non-staff user gets 403, not the manage pages."""
        self.client.force_login(self.regular)
        for url in self.manage_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_forbidden_page_renders_and_offers_a_way_out(self):
        """The 403 is the custom template, not Django's bare default.

        A regular user who lands here is otherwise stuck: signed in, refused,
        with no control to sign out again.
        """
        self.client.force_login(self.regular)
        response = self.client.get(reverse("manage_players"))
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, "<strong>ada</strong>", status_code=403)
        self.assertContains(
            response,
            f'<form method="post" action="{reverse("manage_logout")}"',
            status_code=403,
        )

    def test_regular_user_cannot_post_either(self):
        """The gate covers writes, not just the rendered pages."""
        self.client.force_login(self.regular)
        response = self.client.post(
            reverse("manage_player_add"), {"player_number": "99", "name": "Mallory"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Player.objects.filter(name="Mallory").exists())

    def test_staff_user_is_allowed(self):
        # follow=True because /manage/ itself is a redirect to /manage/players/.
        self.client.force_login(self.staff)
        for url in self.manage_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, follow=True).status_code, 200)

    def test_inactive_staff_is_denied(self):
        """Deactivating an account revokes its access.

        It comes out as a redirect to login rather than a 403 because Django
        never resolves the session: ModelBackend.get_user drops an inactive
        user, so the request arrives anonymous. Deactivating is therefore a
        real off switch, whatever is left in the session table.
        """
        self.client.force_login(self.inactive_staff)
        response = self.client.get(reverse("manage_players"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("manage_login"), response["Location"])

    def test_all_manage_urls_are_covered(self):
        """Every /manage/ URL is either in the matrix above or a login view.

        Guards against a new manage view being added without a gate: it would
        appear here as an untested URL.
        """
        from players import urls as players_urls

        exempt = {"manage_login", "manage_logout"}
        covered = set(MANAGE_URL_NAMES) | {"manage_player_edit"} | exempt
        manage_names = {
            p.name
            for p in players_urls.urlpatterns
            if str(p.pattern).startswith("manage/")
        }
        self.assertEqual(manage_names - covered, set())


class StaffLoginTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="admin", password="pw-admin-1234", is_staff=True
        )
        cls.regular = User.objects.create_user(
            username="ada", password="pw-ada-1234"
        )

    def test_staff_can_log_in(self):
        response = self.client.post(
            reverse("manage_login"),
            {"username": "admin", "password": "pw-admin-1234"},
        )
        self.assertRedirects(response, reverse("manage_players"))

    def test_non_staff_is_refused_with_correct_password(self):
        """Right password, wrong kind of account: refused at the form.

        Letting them log in would leave a session that 403s on every page it
        can reach, with no explanation.
        """
        response = self.client.post(
            reverse("manage_login"), {"username": "ada", "password": "pw-ada-1234"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not an administrator account")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_requires_post(self):
        """Django 5+ dropped GET logout; the templates must use a form."""
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("manage_logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("manage_logout")).status_code, 302)

    def test_manage_page_logout_control_is_a_post_form(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("manage_players"))
        self.assertContains(
            response, f'<form method="post" action="{reverse("manage_logout")}"'
        )


class NavAdminLinkTest(TestCase):
    """The public navbar's Admin link.

    It points at /manage/, which redirects anonymous visitors to the login
    page — that is how an administrator finds the login form. It is hidden
    from a signed-in non-staff user, for whom it would only ever 403.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="admin", password="pw-admin-1234", is_staff=True
        )
        cls.regular = User.objects.create_user(username="ada", password="pw-ada-1234")

    def assertAdminLink(self, present):
        response = self.client.get(reverse("search_page"))
        self.assertEqual(response.status_code, 200)
        assertion = self.assertContains if present else self.assertNotContains
        assertion(response, f'href="{reverse("manage_redirect")}"')

    def test_shown_to_anonymous_visitors(self):
        self.assertAdminLink(True)

    def test_shown_to_staff(self):
        self.client.force_login(self.staff)
        self.assertAdminLink(True)

    def test_hidden_from_regular_users(self):
        self.client.force_login(self.regular)
        self.assertAdminLink(False)

    def test_link_reaches_the_login_page_for_anonymous_visitors(self):
        """The link is only useful if it actually lands somewhere usable."""
        response = self.client.get(reverse("manage_redirect"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "players/manage_login.html")


class UserPlayerLinkTest(TestCase):
    def test_link_is_optional_and_one_to_one(self):
        player = Player.objects.create(player_number="7", name="Grace Hopper")
        user = User.objects.create_user(username="grace", password="pw-grace-1234")
        self.assertIsNone(user.player)

        user.player = player
        user.save()
        self.assertEqual(player.user, user)

    def test_deleting_the_player_keeps_the_account(self):
        """Player rows are re-seeded from data/players.csv on every deploy, so
        the account must not be collateral damage if one is removed."""
        player = Player.objects.create(player_number="8", name="Alan Turing")
        user = User.objects.create_user(
            username="alan", password="pw-alan-1234", player=player
        )
        player.delete()
        user.refresh_from_db()
        self.assertIsNone(user.player)
        self.assertTrue(User.objects.filter(username="alan").exists())
