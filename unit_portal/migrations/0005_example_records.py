import datetime as dt
import json
from pathlib import Path

from django.db import migrations
from django.utils import timezone


def seed_examples(apps, schema_editor):
    alias = schema_editor.connection.alias
    data = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
    users = apps.get_model("auth", "User").objects.using(alias)

    def records(model):
        return apps.get_model("intranet", model).objects.using(alias)

    def timestamp(value):
        if value:
            return timezone.make_aware(dt.datetime.fromisoformat(value))
        return None

    accounts = {}
    for row in data["users"]:
        user, created = users.get_or_create(
            username=f"example-{row['username']}",
            defaults={"is_active": False, "password": "!"},
        )
        if not created and (user.is_active or user.password != "!"):
            raise RuntimeError(f"Demo username is already in use: {user.username}")
        records("Profile").get_or_create(user=user, defaults={
            "name": row["name"], "dept": row["dept"], "title": row["title"],
            "joined": dt.date.fromisoformat(row["joined"]) if row["joined"] else None,
        })
        accounts[row["id"]] = user

    for row in data["notices"]:
        records("Notice").get_or_create(title=row["title"], author=accounts[row["author_id"]], defaults={
            "body": row["body"], "pinned": bool(row["pinned"]), "created": timestamp(row["created"]),
        })
    posts = {}
    for row in data["posts"]:
        posts[row["id"]], _ = records("Post").get_or_create(
            title=row["title"], author=accounts[row["author_id"]], defaults={
                "category": row["category"], "body": row["body"],
                "views": row["views"], "created": timestamp(row["created"]),
            },
        )
    for row in data["comments"]:
        records("Comment").get_or_create(
            post=posts[row["post_id"]], author=accounts[row["author_id"]], body=row["body"],
            defaults={"created": timestamp(row["created"])},
        )
    for row in data["approvals"]:
        records("Approval").get_or_create(
            title=row["title"], drafter=accounts[row["drafter_id"]], approver=accounts[row["approver_id"]],
            defaults={"kind": row["kind"], "body": row["body"], "status": row["status"],
                      "comment": row["comment"] or "", "created": timestamp(row["created"]),
                      "decided": timestamp(row["decided"])},
        )

    # Keep the original spacing of the calendar examples, starting on setup day.
    offset = timezone.localdate() - min(dt.date.fromisoformat(row["date"]) for row in data["events"])
    for row in data["events"]:
        records("Event").get_or_create(title=row["title"], owner=accounts[row["owner_id"]], scope=row["scope"], defaults={
            "date": dt.date.fromisoformat(row["date"]) + offset,
            "time": dt.time.fromisoformat(row["time"]) if row["time"] else None,
            "place": row["place"] or "",
        })

    author = accounts[1]
    for user in users.filter(is_active=True).exclude(id=author.id).iterator():
        records("Approval").get_or_create(
            title="[시연] 정보보안 교육 확인", drafter=author, approver=user,
            defaults={"kind": "품의", "body": "정보보안 교육 일정을 확인하고 결재해 주세요."},
        )


class Migration(migrations.Migration):
    dependencies = [("intranet", "0004_notice_only_username")]
    operations = [migrations.RunPython(seed_examples)]
