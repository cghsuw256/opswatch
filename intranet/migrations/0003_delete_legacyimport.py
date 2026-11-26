from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("intranet", "0002_remove_approval_intranet_approval_kind_and_more"),
    ]

    operations = [
        migrations.DeleteModel(name="LegacyImport"),
    ]
