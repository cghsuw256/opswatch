from django.core.exceptions import ObjectDoesNotExist

from operations.models import Employee

from .models import Profile


def get_profile(user):
    try:
        profile = user.profile
        if profile.legacy_id is None and (not profile.dept or profile.name in (user.get_username(), user.get_full_name())):
            employee = Employee.objects.filter(login_id=user.get_username()).first()
            if employee:
                changed = []
                for field, value in {"name": employee.name, "dept": employee.department, "title": employee.title, "email": employee.email, "ext": employee.extension[:6]}.items():
                    if not getattr(profile, field) or (field == "name" and profile.name in (user.get_username(), user.get_full_name())):
                        setattr(profile, field, value)
                        changed.append(field)
                if changed:
                    profile.save(update_fields=changed)
        return profile
    except ObjectDoesNotExist:
        employee = Employee.objects.filter(login_id=user.get_username()).first()
        defaults = {"name": user.get_full_name() or user.get_username(), "email": user.email}
        if employee:
            defaults.update(name=employee.name, dept=employee.department, title=employee.title, email=employee.email, ext=employee.extension[:6])
        profile, _ = Profile.objects.get_or_create(user=user, defaults=defaults)
        return profile
