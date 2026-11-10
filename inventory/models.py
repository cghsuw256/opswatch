from django.db import models


class Employee(models.Model):
    name = models.CharField(max_length=64)
    department = models.CharField(max_length=64)
    title = models.CharField(max_length=64)
    email = models.EmailField(unique=True)
    login_id = models.CharField(max_length=32, blank=True)
    extension = models.CharField(max_length=16, blank=True)
    duty = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["department", "name"]

    def __str__(self):
        return f"{self.name} ({self.department})"


class Server(models.Model):
    STATUS_OK = "ok"
    STATUS_WARN = "warn"
    STATUS_DOWN = "down"
    STATUS_CHOICES = [
        (STATUS_OK, "정상"),
        (STATUS_WARN, "주의"),
        (STATUS_DOWN, "장애"),
    ]

    hostname = models.CharField(max_length=64, unique=True)
    address = models.CharField(max_length=64)
    role = models.CharField(max_length=64)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_OK)
    cpu_percent = models.PositiveSmallIntegerField()
    memory_percent = models.PositiveSmallIntegerField()
    location = models.CharField(max_length=64)
    seed_metrics = models.BooleanField(default=True)

    class Meta:
        ordering = ["hostname"]

    def __str__(self):
        return self.hostname


class Inspection(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="inspections")
    inspected_at = models.DateTimeField()
    inspector_name = models.CharField(max_length=64)
    summary = models.CharField(max_length=160)
    detail = models.TextField()
    passed = models.BooleanField(default=True)

    class Meta:
        ordering = ["-inspected_at"]

    def __str__(self):
        return f"{self.server.hostname} {self.inspected_at.isoformat()}"
