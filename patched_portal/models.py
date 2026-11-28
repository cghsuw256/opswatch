from django.db import models


class LoginAttempt(models.Model):
    source = models.CharField(max_length=45, primary_key=True)
    window = models.PositiveBigIntegerField(db_index=True)
    count = models.PositiveSmallIntegerField(default=0)
