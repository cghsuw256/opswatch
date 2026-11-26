import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64)),
                ("department", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=64)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("login_id", models.CharField(blank=True, max_length=32)),
                ("extension", models.CharField(blank=True, max_length=16)),
                ("duty", models.CharField(blank=True, max_length=160)),
            ],
            options={"ordering": ["department", "name"]},
        ),
        migrations.CreateModel(
            name="Server",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hostname", models.CharField(max_length=64, unique=True)),
                ("address", models.CharField(max_length=64)),
                ("role", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[("ok", "정상"), ("warn", "주의"), ("down", "장애")],
                        default="ok",
                        max_length=8,
                    ),
                ),
                ("cpu_percent", models.PositiveSmallIntegerField()),
                ("memory_percent", models.PositiveSmallIntegerField()),
                ("location", models.CharField(max_length=64)),
                ("seed_metrics", models.BooleanField(default=True)),
            ],
            options={"ordering": ["hostname"]},
        ),
        migrations.CreateModel(
            name="Inspection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inspected_at", models.DateTimeField()),
                ("inspector_name", models.CharField(max_length=64)),
                ("summary", models.CharField(max_length=160)),
                ("detail", models.TextField()),
                ("passed", models.BooleanField(default=True)),
                (
                    "server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inspections",
                        to="inventory.server",
                    ),
                ),
            ],
            options={"ordering": ["-inspected_at"]},
        ),
    ]
