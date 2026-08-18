from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class StaffAuthenticationForm(AuthenticationForm):
    """Login form for /manage: rejects correct credentials for non-staff.

    Without this, a regular user who logs in here lands on a 403 with no
    explanation. Refusing at the form says what actually happened, and leaves
    them logged out rather than in a session they cannot use anywhere on this
    page.
    """

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError(
                "This account is not an administrator account.",
                code="not_staff",
            )
