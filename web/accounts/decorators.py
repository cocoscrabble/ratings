"""Access control for the staff-only sections of the site.

``login_required`` is not enough here. It answers "is this someone?", but the
``/manage`` section asks "is this an administrator?" — it can rewrite player
identity and bulk-import the whole player list. As soon as non-staff accounts
exist, ``login_required`` would hand every one of them those powers.
"""

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url


def staff_required(view_func):
    """Allow only active ``is_staff`` users; 403 for anyone else logged in.

    Anonymous visitors are sent to the login page, as usual. An authenticated
    non-staff user gets a flat 403 rather than a redirect: bouncing them to the
    login page would loop, since they are already logged in and the login view
    would send them straight back here.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            if user.is_active and user.is_staff:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return redirect_to_login(
            request.get_full_path(), resolve_url(settings.LOGIN_URL)
        )

    return _wrapped
