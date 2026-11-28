from django.contrib.auth import get_user_model

from .models import Approval


def seed_example_approval(user):
    author = get_user_model().objects.filter(username="example-admin", is_active=False).first()
    if author is not None:
        Approval.objects.get_or_create(
            title="[시연] 정보보안 교육 확인", drafter=author, approver=user,
            defaults={"kind": "품의", "body": "정보보안 교육 일정을 확인하고 결재해 주세요."},
        )
