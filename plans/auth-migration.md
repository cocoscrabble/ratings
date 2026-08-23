# Note: the custom user model swap (done)

**Status: complete.** Applied to production in August 2026, with the code in
`b8e45dc`. Nothing here is outstanding; this is kept as the record of why the
`accounts` app exists and what it cost, since neither is visible in a diff.

## What changed

The site moved from Django's built-in `auth.User` to
`AUTH_USER_MODEL = "accounts.User"` (`web/accounts/models.py`). The reason was
timing rather than any feature: swapping the user model is cheap while the only
accounts are a handful of administrators, and expensive once real users exist.
Doing it up front means the planned regular-user work — profile fields, or
moving the login identity to email — is an ordinary migration.

The same commit closed the gap that made it urgent: `/manage` was gated on
`login_required`, which only asks "is this someone?". It can rewrite player
identity and bulk-import the player list, so the first non-staff account would
have inherited those powers. It is now gated on `is_staff`
(`accounts.decorators.staff_required`).

## Why it needed a manual database step

`django.contrib.admin`'s `LogEntry` has a foreign key to whatever
`AUTH_USER_MODEL` points at. On the live database that dependency had been
resolved to `auth.User` and applied long before, so once it resolved to
`accounts.User` instead, `migrate` refused to run:

```
django.db.migrations.exceptions.InconsistentMigrationHistory:
Migration admin.0001_initial is applied before its dependency accounts.0001_initial
```

Django stops rather than leave `django_admin_log.user_id` pointing at a table
that is no longer the user table. The fix was to un-apply `admin` (drop
`django_admin_log`, delete its `django_migrations` rows), deploy so that
`accounts_user` was created, then `INSERT ... SELECT` the rows across from
`auth_user` and advance the id sequence. Existing accounts and password hashes
were preserved — nobody needed a password reset.

Worth knowing if it ever comes up again: the `auth` app's migrations can stay
recorded as applied. `auth.0001_initial` creates `User` with
`options={'swappable': 'AUTH_USER_MODEL'}`, which Django skips at the database
level once the model is swapped away, so `auth_user` is simply never created on
a fresh database. `auth_group` and `auth_permission` belong to the permissions
framework, not the user model, and stay in use.

## Setting up a database now

There is no special procedure any more — a database created from scratch gets
the right schema from `migrate` alone.

```bash
make run        # migrate, seed identity from data/players.csv, build ratings
uv run --extra web python web/manage.py createsuperuser
```

In production, `dokku run cocodb python web/manage.py createsuperuser` (over
`ssh -t`, since it prompts). Accounts are otherwise managed in `/django-admin/`:
creating staff, resetting passwords, and linking an account to its player. There
is no mail service configured, so there is no self-service password reset.
