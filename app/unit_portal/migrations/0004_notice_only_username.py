from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("intranet", "0003_delete_legacyimport"),
    ]

    operations = [
        migrations.AddField(
            model_name="notice",
            name="only_username",
            field=models.CharField(blank=True, max_length=150, verbose_name="열람 계정"),
        ),
    ]
