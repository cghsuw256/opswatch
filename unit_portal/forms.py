import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError

from .models import Approval, Comment, Event, Notice, Post, Profile


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ("title", "body", "pinned")
        widgets = {"body": forms.Textarea(attrs={"rows": 12})}


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ("category", "title", "body")
        widgets = {"body": forms.Textarea(attrs={"rows": 12})}


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "댓글을 입력하세요"})}


class ApproverChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        profile = user.profile
        return f"{profile.dept} · {profile.title} {profile.name}"


class ApprovalForm(forms.ModelForm):
    approver = ApproverChoiceField(label="결재자", queryset=get_user_model().objects.none())

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["approver"].queryset = get_user_model().objects.exclude(pk=user.pk).filter(is_active=True).select_related("profile").order_by("profile__dept", "profile__name", "username")

    class Meta:
        model = Approval
        fields = ("kind", "approver", "title", "body")
        widgets = {"body": forms.Textarea(attrs={"rows": 10})}


class DecisionForm(forms.Form):
    comment = forms.CharField(label="의견 (선택)", max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    action = forms.ChoiceField(choices=(("approve", "승인"), ("reject", "반려")), widget=forms.HiddenInput)


class EventForm(forms.ModelForm):
    def __init__(self, *args, is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not is_admin:
            self.fields["scope"].choices = (("personal", "개인"),)
            self.fields["scope"].widget = forms.HiddenInput()
            self.fields["scope"].required = False

    def clean_scope(self):
        return self.cleaned_data.get("scope") or "personal"

    class Meta:
        model = Event
        fields = ("title", "date", "time", "place", "scope")
        widgets = {"date": forms.DateInput(attrs={"type": "date"}), "time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}


class ProfileForm(forms.ModelForm):
    phone = forms.RegexField(label="휴대폰", regex=r"^[0-9\-+ ]*$", max_length=20, required=False, error_messages={"invalid": "전화번호에는 숫자, 공백, +, -만 입력해 주세요."})
    ext = forms.RegexField(label="군 전화", regex=r"^[0-9]*$", max_length=6, required=False, error_messages={"invalid": "군 전화에는 숫자만 입력해 주세요."})

    class Meta:
        model = Profile
        fields = ("phone", "ext")


class IntranetPasswordChangeForm(PasswordChangeForm):
    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1", "")
        if not (8 <= len(password) <= 200) or not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
            raise ValidationError("비밀번호는 8~200자이며 영문과 숫자를 모두 포함해야 합니다.")
        if password.lower() == self.user.get_username().lower() or self.user.check_password(password):
            raise ValidationError("아이디와 같거나 기존과 같은 비밀번호는 쓸 수 없습니다.")
        return password
