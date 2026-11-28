from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="LoginAttempt",
            fields=[
                ("source", models.CharField(max_length=45, primary_key=True, serialize=False)),
                ("window", models.PositiveBigIntegerField(db_index=True)),
                ("count", models.PositiveSmallIntegerField(default=0)),
            ],
        ),
    ]
