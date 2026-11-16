import hashlib
import sqlite3
from contextlib import closing
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from intranet.models import Approval, Comment, Event, Notice, Post, Profile


class LegacyImportTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.source = Path(directory.name) / "intranet.db"
        salt = bytes.fromhex("00112233445566778899aabbccddeeff")
        digest = hashlib.pbkdf2_hmac("sha256", b"Legacy1234", salt, 200_000).hex()
        self.legacy_hash = salt.hex() + "$" + digest
        with closing(sqlite3.connect(self.source)) as db, db:
            db.executescript("""
                CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, pw TEXT, name TEXT,
                    dept TEXT, title TEXT, email TEXT, phone TEXT, ext TEXT, role TEXT, joined TEXT);
                CREATE TABLE notices (id INTEGER PRIMARY KEY, title TEXT, body TEXT, author_id INTEGER,
                    pinned INTEGER, created TEXT);
                CREATE TABLE posts (id INTEGER PRIMARY KEY, category TEXT, title TEXT, body TEXT,
                    author_id INTEGER, views INTEGER, created TEXT);
                CREATE TABLE comments (id INTEGER PRIMARY KEY, post_id INTEGER, author_id INTEGER,
                    body TEXT, created TEXT);
                CREATE TABLE approvals (id INTEGER PRIMARY KEY, kind TEXT, title TEXT, body TEXT,
                    drafter_id INTEGER, approver_id INTEGER, status TEXT, comment TEXT, created TEXT, decided TEXT);
                CREATE TABLE events (id INTEGER PRIMARY KEY, title TEXT, date TEXT, time TEXT,
                    place TEXT, owner_id INTEGER, scope TEXT);
            """)
            for pk, username, role in ((1, "source_admin", "admin"), (2, "source_member", "user")):
                db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                    pk, username, self.legacy_hash, username, "통신소대", "중위",
                    username + "@example.test", "010-1234-5678", "9200", role, "2026-01-01",
                ))
            db.execute("INSERT INTO notices VALUES (1,'원본 공지','공지 내용',1,1,'2026-11-01 09:00')")
            db.execute("INSERT INTO posts VALUES (1,'정보공유','원본 게시글','게시글 내용',2,7,'2026-11-01 10:00')")
            db.execute("INSERT INTO comments VALUES (1,1,1,'답변 내용','2026-11-01 11:00')")
            db.execute("INSERT INTO approvals VALUES (1,'지출결의','원본 결재','결재 내용',2,1,'pending',NULL,'2026-11-01 12:00',NULL)")
            db.execute("INSERT INTO events VALUES (1,'원본 일정','2026-11-20','10:00','회의실',1,'company')")

    def import_source(self):
        call_command("import_intranet", source=str(self.source), stdout=StringIO())

    def test_import_preserves_password_relations_and_subsequent_edits_and_deletes(self):
        self.import_source()
        admin = get_user_model().objects.get(username="source_admin")
        member = get_user_model().objects.get(username="source_member")
        self.assertTrue(admin.check_password("Legacy1234"))
        admin.refresh_from_db()
        self.assertTrue(admin.password.startswith("pbkdf2_sha256$"))
        self.assertFalse(admin.is_staff)
        self.assertFalse(admin.is_superuser)
        self.assertEqual(Profile.objects.get(user=admin).role, "admin")
        post = Post.objects.get(title="원본 게시글")
        self.assertEqual(post.author, member)
        self.assertEqual(Comment.objects.get(post=post).author, admin)
        self.assertEqual(Approval.objects.get().approver, admin)
        self.assertEqual(Event.objects.get().owner, admin)
        post.title = "이관 후 수정"
        post.save()
        Notice.objects.get().delete()
        self.import_source()
        self.assertEqual(Post.objects.get().title, "이관 후 수정")
        self.assertFalse(Notice.objects.exists())
        self.assertEqual(Comment.objects.count(), 1)
        admin.refresh_from_db()
        self.assertTrue(admin.password.startswith("pbkdf2_sha256$"))

    def test_matching_account_keeps_existing_password_and_profile(self):
        member = get_user_model().objects.create_user("source_member", password="Local5678")
        Profile.objects.update_or_create(user=member, defaults={"name": "기존 이름", "phone": "010-9999-9999"})
        self.import_source()
        member.refresh_from_db()
        self.assertTrue(member.check_password("Local5678"))
        self.assertFalse(member.check_password("Legacy1234"))
        profile = Profile.objects.get(user=member)
        self.assertEqual(profile.name, "기존 이름")
        self.assertEqual(profile.phone, "010-9999-9999")
        self.assertEqual(Post.objects.get().author, member)
