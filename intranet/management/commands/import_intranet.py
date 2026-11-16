from contextlib import closing
import datetime as dt
from pathlib import Path
import sqlite3

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from intranet.models import Approval, Comment, Event, LegacyImport, Notice, Post
from intranet.profiles import get_profile


class Command(BaseCommand):
    help = "Import original intranet SQLite data once per source ID without overwriting existing users or content."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=Path, default=settings.BASE_DIR / "파이선" / "intranet.db")

    def handle(self, *args, **options):
        source = Path(options["source"]).resolve()
        if not source.is_file():
            raise CommandError(f"Legacy intranet database not found: {source}")
        try:
            with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as legacy:
                legacy.row_factory = sqlite3.Row
                # No sessions are imported: only Django authentication is used.
                rows = {table: list(legacy.execute(f"SELECT * FROM {table} ORDER BY id")) for table in ("users", "notices", "posts", "comments", "approvals", "events")}
            with transaction.atomic():
                counts = self.import_rows(rows)
        except (sqlite3.Error, ValueError, TypeError, KeyError, IntegrityError) as exc:
            raise CommandError(f"Could not import legacy intranet data: {exc}") from exc
        self.stdout.write(self.style.SUCCESS("Intranet import complete: " + ", ".join(f"{table}={count}" for table, count in counts.items()) + " newly imported. Existing records unchanged."))

    @staticmethod
    def timestamp(value):
        if not value:
            return None
        result = dt.datetime.fromisoformat(value)
        return timezone.make_aware(result, timezone.get_default_timezone()) if timezone.is_naive(result) else result

    @staticmethod
    def password(value):
        salt, digest = value.split("$")
        if len(salt) != 32 or len(digest) != 64:
            raise ValueError("Invalid legacy PBKDF2 password length")
        bytes.fromhex(salt)
        bytes.fromhex(digest)
        return f"legacy_pbkdf2_sha256$200000${salt}${digest}"

    def import_rows(self, rows):
        user_model = get_user_model()
        counts = {table: 0 for table in rows}
        mappings = {(record.table, record.source_id): record.target_id for record in LegacyImport.objects.all()}
        users = {}
        for row in rows["users"]:
            key = ("users", row["id"])
            if key in mappings:
                user = user_model.objects.filter(pk=mappings[key]).first()
                if user is not None:
                    get_profile(user)
                    users[row["id"]] = user.pk
                continue
            user, created = user_model.objects.get_or_create(username=row["username"], defaults={"password": self.password(row["pw"]), "email": row["email"] or ""})
            profile = get_profile(user)
            if profile.legacy_id not in (None, row["id"]):
                raise CommandError(f"User {user.username} is already mapped to a different legacy identity")
            if created:
                for field in ("name", "dept", "title", "email", "phone", "ext", "role"):
                    setattr(profile, field, row[field] or "")
                profile.joined = dt.date.fromisoformat(row["joined"]) if row["joined"] else None
                counts["users"] += 1
            profile.legacy_id = row["id"]
            profile.save()
            LegacyImport.objects.create(table="users", source_id=row["id"], target_id=user.pk)
            mappings[key] = user.pk
            users[row["id"]] = user.pk

        # Existing OpsWatch users get non-admin profiles using their Employee record.
        for user in user_model.objects.all().iterator():
            get_profile(user)

        def user_id(source_id):
            if source_id not in users:
                raise CommandError(f"Legacy user {source_id} is missing or its mapped Django user was removed")
            return users[source_id]

        models = {"notices": Notice, "posts": Post, "comments": Comment, "approvals": Approval, "events": Event}
        for table, model in models.items():
            for row in rows[table]:
                key = (table, row["id"])
                if key in mappings:
                    continue
                if table == "comments":
                    post_id = mappings.get(("posts", row["post_id"]))
                    if post_id is None:
                        raise CommandError(f"Comment {row['id']} references unknown legacy post {row['post_id']}")
                    if not Post.objects.filter(pk=post_id).exists():
                        # Deleted target posts remain deleted, even if new legacy comments exist.
                        LegacyImport.objects.create(table=table, source_id=row["id"], target_id=0)
                        mappings[key] = 0
                        continue
                    fields = {"post_id": post_id, "author_id": user_id(row["author_id"]), "body": row["body"], "created": self.timestamp(row["created"])}
                elif table == "events":
                    fields = {"title": row["title"], "date": dt.date.fromisoformat(row["date"]), "time": dt.time.fromisoformat(row["time"]) if row["time"] else None, "place": row["place"] or "", "owner_id": user_id(row["owner_id"]), "scope": row["scope"]}
                elif table == "approvals":
                    fields = {"kind": row["kind"], "title": row["title"], "body": row["body"], "drafter_id": user_id(row["drafter_id"]), "approver_id": user_id(row["approver_id"]), "status": row["status"], "comment": row["comment"] or "", "created": self.timestamp(row["created"]), "decided": self.timestamp(row["decided"])}
                else:
                    fields = {"title": row["title"], "body": row["body"], "author_id": user_id(row["author_id"]), "created": self.timestamp(row["created"])}
                    if table == "notices":
                        fields["pinned"] = bool(row["pinned"])
                    else:
                        fields.update(category=row["category"], views=row["views"])
                record = model.objects.create(**fields)
                LegacyImport.objects.create(table=table, source_id=row["id"], target_id=record.pk)
                mappings[key] = record.pk
                counts[table] += 1
        return counts
