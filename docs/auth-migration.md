# One-time: migrating the live database to the custom user model

Adding `AUTH_USER_MODEL = "accounts.User"` changes which table Django's users
live in. A database that already ran `migrate` against the built-in
`auth.User` cannot simply have the new migration applied on top: the release
phase will stop with

```
django.db.migrations.exceptions.InconsistentMigrationHistory:
Migration admin.0001_initial is applied before its dependency accounts.0001_initial
```

This is a **safe** failure — it happens during `release`, so Dokku aborts the
deploy and leaves the running version up. But the deploy will not succeed until
the steps below are run against the production database.

Existing accounts (usernames, password hashes, staff/superuser flags) are
**preserved**. Nobody has to have their password reset.

## Why the failure happens

`django.contrib.admin`'s `LogEntry` has a foreign key to whatever
`AUTH_USER_MODEL` points at, so `admin.0001_initial` depends on it. On the live
DB that dependency was resolved to `auth.User` and applied long ago; now it
resolves to `accounts.User`, a migration that has never run. Django refuses to
proceed rather than leave `django_admin_log.user_id` pointing at a table that is
no longer the user table.

The fix is to un-apply `admin`, create `accounts_user`, copy the rows across,
and let `admin` re-apply against the new target.

## Procedure

Run this **before** (or immediately after the first failed) deploy of the commit
that introduces `accounts`. `$PG` is the Postgres service name — find it with
`dokku postgres:list`.

### 1. Back up

```bash
dokku postgres:export $PG > cocodb-pre-auth-$(date +%F).dump
```

Keep this until the site is verified. Restore with `dokku postgres:import $PG <
cocodb-pre-auth-<date>.dump`.

### 2. Detach the admin app from the old user table

```bash
dokku postgres:connect $PG
```

```sql
DROP TABLE IF EXISTS django_admin_log;
DELETE FROM django_migrations WHERE app = 'admin';
```

`django_admin_log` is an audit trail of edits made through `/django-admin/`. It
is not referenced by anything else and is not a source of truth; dropping it
loses that history and nothing more.

### 3. Deploy, then create the new user table

```bash
git push origin main           # or ./scripts/deploy.sh
```

With `admin` un-applied, the release phase's `migrate` gets past the consistency
check and applies `accounts` and `admin` by itself — no manual command needed.
(If you are doing this without deploying, the equivalent is
`dokku run cocodb python web/manage.py migrate`.)

Between this step and the next the site is up but has **no accounts**, so
`/manage` cannot be logged into. The public pages are unaffected.

### 4. Copy the accounts across

```bash
dokku postgres:connect $PG
```

```sql
INSERT INTO accounts_user
    (id, password, last_login, is_superuser, username, first_name, last_name,
     email, is_staff, is_active, date_joined, player_id)
SELECT id, password, last_login, is_superuser, username, first_name, last_name,
       email, is_staff, is_active, date_joined, NULL
FROM auth_user;

INSERT INTO accounts_user_groups (user_id, group_id)
SELECT user_id, group_id FROM auth_user_groups;

INSERT INTO accounts_user_user_permissions (user_id, permission_id)
SELECT user_id, permission_id FROM auth_user_user_permissions;

SELECT setval(
    pg_get_serial_sequence('accounts_user', 'id'),
    COALESCE((SELECT MAX(id) FROM accounts_user), 1)
);
```

The `setval` matters on Postgres: the rows carry their original ids, so the
sequence must be advanced past them or the next account created will collide.
(SQLite has no sequence to fix.)

### 5. Verify, then drop the old tables

Log in at `/manage/login/` with an existing admin account — the old password
still works. Then:

```sql
DROP TABLE IF EXISTS auth_user_groups, auth_user_user_permissions, auth_user;
```

Leave `auth_group` and `auth_permission` alone: those belong to the permissions
framework, not to the user model, and are still in use.

## If there is no account to log in with

```bash
dokku run cocodb python web/manage.py createsuperuser
```

## Local development

No procedure needed — delete `web/db.sqlite3` and run `make run`, which
migrates, re-seeds identity from `data/players.csv` and rebuilds the ratings
projection. Then `python web/manage.py createsuperuser`.
