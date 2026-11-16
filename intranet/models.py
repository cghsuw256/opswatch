from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


CATEGORIES = ("자유", "질문", "교육자료", "정보공유", "경조사")
APPROVAL_KINDS = ("휴가", "외출·외박", "물자청구", "출장", "지출결의", "품의")


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    legacy_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    name = models.CharField("이름", max_length=150)
    dept = models.CharField("부서", max_length=100, blank=True)
    title = models.CharField("계급·직책", max_length=100, blank=True)
    email = models.EmailField("메일", blank=True)
    phone = models.CharField("휴대폰", max_length=20, blank=True)
    ext = models.CharField("군 전화", max_length=6, blank=True)
    role = models.CharField(max_length=10, choices=(("user", "일반"), ("admin", "관리자")), default="user")
    joined = models.DateField("전입일", null=True, blank=True)

    class Meta:
        ordering = ("dept", "joined", "name", "pk")
        constraints = [models.CheckConstraint(condition=Q(role__in=("user", "admin")), name="intranet_profile_role")]

    @property
    def is_admin(self):
        return self.role == "admin"

    def __str__(self):
        return self.name or self.user.get_username()


class Notice(models.Model):
    title = models.CharField("제목", max_length=120)
    body = models.TextField("내용", max_length=5000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="intranet_notices")
    pinned = models.BooleanField("상단에 고정", default=False)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-pinned", "-created", "-pk")


class Post(models.Model):
    category = models.CharField("분류", max_length=20, choices=tuple((value, value) for value in CATEGORIES))
    title = models.CharField("제목", max_length=120)
    body = models.TextField("내용", max_length=5000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="intranet_posts")
    views = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created", "-pk")
        constraints = [models.CheckConstraint(condition=Q(category__in=CATEGORIES), name="intranet_post_category")]


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="intranet_comments")
    body = models.TextField("댓글", max_length=1000)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("pk",)


class Approval(models.Model):
    kind = models.CharField("문서 종류", max_length=20, choices=tuple((value, value) for value in APPROVAL_KINDS))
    title = models.CharField("제목", max_length=120)
    body = models.TextField("내용", max_length=5000)
    drafter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="drafted_approvals")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_approvals")
    status = models.CharField(max_length=10, choices=(("pending", "대기"), ("approved", "승인"), ("rejected", "반려")), default="pending")
    comment = models.TextField("결재 의견", max_length=500, blank=True)
    created = models.DateTimeField(default=timezone.now)
    decided = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created", "-pk")
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=APPROVAL_KINDS), name="intranet_approval_kind"),
            models.CheckConstraint(condition=Q(status__in=("pending", "approved", "rejected")), name="intranet_approval_status"),
            models.CheckConstraint(condition=~Q(drafter=F("approver")), name="intranet_approval_distinct_users"),
            models.CheckConstraint(condition=(Q(status="pending", decided__isnull=True) | Q(status__in=("approved", "rejected"), decided__isnull=False)), name="intranet_approval_decided_state"),
        ]
        indexes = [models.Index(fields=("approver", "status"), name="intranet_approval_inbox")]


class Event(models.Model):
    title = models.CharField("제목", max_length=60)
    date = models.DateField("날짜")
    time = models.TimeField("시간", null=True, blank=True)
    place = models.CharField("장소", max_length=40, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="intranet_events")
    scope = models.CharField("구분", max_length=10, choices=(("personal", "개인"), ("company", "부대")), default="personal")

    class Meta:
        ordering = ("date", "time", "pk")
        constraints = [models.CheckConstraint(condition=Q(scope__in=("personal", "company")), name="intranet_event_scope")]
        indexes = [models.Index(fields=("date", "scope"), name="intranet_event_calendar")]


class LegacyImport(models.Model):
    """Permanent source identity mapping, retained when imported content is deleted."""

    table = models.CharField(max_length=20)
    source_id = models.PositiveIntegerField()
    target_id = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("table", "source_id"), name="intranet_legacy_identity")]
