# Database Migration Guide

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations with async PostgreSQL support.

## Setup

Alembic configuration lives in the `migrations/` directory:

```
migrations/
├── alembic.ini          # Alembic configuration
└── alembic/
    ├── env.py           # Migration environment (async engine)
    ├── script.py.mako   # Migration file template
    └── versions/        # Migration files
```

The database URL is loaded from the application settings (`api.core.config`), so it reads from your `.env` file automatically.

## Common Commands

All commands should be run from the `migrations/` directory:

```bash
cd migrations
```

### Apply All Migrations

```bash
alembic upgrade head
```

### Rollback One Migration

```bash
alembic downgrade -1
```

### Rollback to a Specific Revision

```bash
alembic downgrade <revision_id>
```

### Rollback Everything

```bash
alembic downgrade base
```

### Check Current Revision

```bash
alembic current
```

### View Migration History

```bash
alembic history --verbose
```

## Creating New Migrations

### Auto-generate from Model Changes

After modifying SQLAlchemy models in `api/models/`, auto-generate a migration:

```bash
alembic revision --autogenerate -m "Add new_column to users"
```

This compares the current model definitions to the database schema and generates the appropriate migration.

**Always review the generated migration** before applying it. Auto-generation may not catch:
- Table or column renames (it will drop + create instead)
- Changes to server defaults
- Custom constraints or triggers

### Create an Empty Migration

For manual migrations (data migrations, custom SQL):

```bash
alembic revision -m "Backfill user display names"
```

Then edit the generated file to add your `upgrade()` and `downgrade()` logic.

## Migration File Structure

```python
"""Description of the migration.

Revision ID: abc123
Revises: def456
Create Date: 2025-01-01 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "abc123"
down_revision = "def456"

def upgrade() -> None:
    # Apply changes
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))

def downgrade() -> None:
    # Reverse changes
    op.drop_column("users", "phone")
```

## Initial Migration

The initial migration (`001_initial_migration.py`) creates all 7 tables:

1. `users` - User accounts
2. `roles` - RBAC roles
3. `user_roles` - User-role junction table
4. `audit_logs` - Audit trail
5. `bot_settings` - Guild-specific settings
6. `modules` - Bot modules
7. `api_keys` - API authentication keys

## Best Practices

1. **One migration per change** - Keep migrations focused and atomic.
2. **Always write downgrade** - Ensure every migration can be reversed.
3. **Review auto-generated migrations** - Don't blindly apply them.
4. **Test migrations** - Run `upgrade` and `downgrade` locally before deploying.
5. **Never edit applied migrations** - Create a new migration to fix issues.
6. **Use meaningful names** - `add_phone_to_users` not `migration_42`.

## Troubleshooting

### "Target database is not up to date"

```bash
alembic stamp head  # Mark DB as current
alembic upgrade head  # Then apply new migrations
```

### "Can't locate revision"

The revisions chain is broken. Check `alembic history` and fix `down_revision` pointers.

### "Table already exists"

The database has tables that aren't tracked by Alembic. Either:
1. Drop all tables and re-run migrations, or
2. Stamp the current revision: `alembic stamp <revision>`
