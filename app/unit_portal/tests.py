from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from unit_portal.models import Profile


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class IntranetBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user("author", password="Original-sample-1234")
        Profile.objects.update_or_create(user=cls.author, defaults={"name": cls.author.username})

    def setUp(self):
        self.client.force_login(self.author)

    def test_password_change_keeps_current_session_and_revokes_other_session(self):
        second = Client()
        self.assertTrue(second.login(username="author", password="Original-sample-1234"))
        response = self.client.post(reverse("intranet:password"), {
            "old_password": "Original-sample-1234",
            "new_password1": "Changed-sample-5678",
            "new_password2": "Changed-sample-5678",
        })
        self.assertEqual(response.status_code, 302)
        self.author.refresh_from_db()
        self.assertTrue(self.author.check_password("Changed-sample-5678"))
        self.assertEqual(self.client.get(reverse("intranet:home")).status_code, 200)
        self.assertEqual(second.get(reverse("intranet:home")).status_code, 302)

    def test_native_forms_reject_missing_csrf(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.author)
        response = protected.post(reverse("intranet:password"), {
            "old_password": "Original-sample-1234",
            "new_password1": "Changed-sample-5678",
            "new_password2": "Changed-sample-5678",
        })
        self.assertEqual(response.status_code, 403)
        self.author.refresh_from_db()
        self.assertTrue(self.author.check_password("Original-sample-1234"))
