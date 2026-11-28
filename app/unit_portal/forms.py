import re

from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError


class IntranetPasswordChangeForm(PasswordChangeForm):
    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1", "")
        if not (8 <= len(password) <= 200) or not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
            raise ValidationError("비밀번호는 8~200자이며 영문과 숫자를 모두 포함해야 합니다.")
        if password.lower() == self.user.get_username().lower() or self.user.check_password(password):
            raise ValidationError("아이디와 같거나 기존과 같은 비밀번호는 쓸 수 없습니다.")
        return password
