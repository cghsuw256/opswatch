from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from unit_portal.models import Approval, Event, Post, Profile


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class IntranetBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user("author", password="Original-sample-1234")
        cls.approver = get_user_model().objects.create_user("approver")
        cls.other = get_user_model().objects.create_user("other")
        Profile.objects.update_or_create(user=cls.author, defaults={"name": cls.author.username})

    def setUp(self):
        self.client.force_login(self.author)

    def test_board_escapes_content_and_enforces_delete_ownership(self):
        response = self.client.post(reverse("intranet:post_new"), {
            "category": "질문", "title": "<script>alert(1)</script>", "body": "<img src=x onerror=alert(1)>",
        })
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get(author=self.author)
        detail = self.client.get(response["Location"])
        self.assertContains(detail, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(detail, "<img src=x onerror=alert(1)>")
        self.client.force_login(self.other)
        denied = self.client.post(reverse("intranet:post_delete", args=[post.pk]))
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        self.client.force_login(self.author)
        self.client.post(reverse("intranet:post_delete", args=[post.pk]))
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())

    def test_approval_is_private_and_cannot_be_decided_twice(self):
        response = self.client.post(reverse("intranet:approval_new"), {
            "kind": "휴가", "title": "개인 결재 문서", "body": "비공개 내용", "approver": self.approver.pk,
        })
        self.assertEqual(response.status_code, 302)
        approval = Approval.objects.get(drafter=self.author)
        detail_url = reverse("intranet:approval_detail", args=[approval.pk])
        decision_url = reverse("intranet:approval_decide", args=[approval.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.assertEqual(self.client.post(decision_url, {"action": "approve"}).status_code, 404)
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(decision_url, {"action": "approve"}).status_code, 403)
        self.client.force_login(self.approver)
        self.assertEqual(self.client.post(decision_url, {"action": "approve", "comment": "확인"}).status_code, 302)
        self.assertEqual(self.client.post(decision_url, {"action": "reject"}).status_code, 403)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "approved")
        self.assertEqual(approval.comment, "확인")

    def test_non_admin_event_stays_private_and_cannot_be_deleted_by_others(self):
        today = date.today().isoformat()
        response = self.client.post(reverse("intranet:event_create"), {
            "title": "개인 일정 비공개", "date": today, "time": "10:30", "place": "회의실", "scope": "company",
        })
        self.assertEqual(response.status_code, 302)
        event = Event.objects.get(owner=self.author)
        self.assertEqual(event.scope, "personal")
        self.client.force_login(self.other)
        calendar = self.client.get(reverse("intranet:calendar"), {"ym": today[:7]})
        self.assertNotContains(calendar, "개인 일정 비공개")
        self.assertEqual(self.client.post(reverse("intranet:event_delete", args=[event.pk])).status_code, 403)
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())


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


    def test_people_search_is_private_and_filters_the_directory(self):
        people = reverse("intranet:people")
        self.assertRedirects(Client().get(people), f"/login/?next={people}")
        Profile.objects.filter(user=self.approver).update(name="Directory target", dept="Engineering")
        result = self.client.get(people, {"q": "Directory target", "dept": "Engineering"})
        self.assertContains(result, "Directory target")
        self.assertNotContains(result, "other")
