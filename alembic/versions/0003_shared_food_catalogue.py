"""shared food catalogue with personal overrides

Every food becomes visible to all users; foods.owner_id becomes created_by_id
(the contributor). Users keep their own nutrition values in food_overrides.

Existing foods with the same name (case-insensitive) are merged into one: the
curated one if any, else the oldest. A merged user's differing values become
their personal override, and diary entries are repointed. Downgrade does not
split merged foods back apart.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NUTRIENTS = ("kcal", "protein", "fat", "carbs")


def _merge_duplicate_names(conn) -> None:
    rows = conn.execute(sa.text(
        "SELECT id, created_by_id, kcal, protein, fat, carbs, lower(btrim(name)) AS key FROM foods "
        "ORDER BY lower(btrim(name)), created_by_id IS NOT NULL, id"
    )).mappings().all()
    keep = None
    for row in rows:
        if keep is None or row["key"] != keep["key"]:
            keep = row
            continue
        if row["created_by_id"] is not None and any(row[n] != keep[n] for n in NUTRIENTS):
            conn.execute(sa.text(
                "INSERT INTO food_overrides (user_id, food_id, kcal, protein, fat, carbs) "
                "VALUES (:user, :food, :kcal, :protein, :fat, :carbs) ON CONFLICT DO NOTHING"
            ), {"user": row["created_by_id"], "food": keep["id"], **{n: row[n] for n in NUTRIENTS}})
        conn.execute(sa.text("UPDATE diary_entries SET food_id = :keep WHERE food_id = :dup"),
                     {"keep": keep["id"], "dup": row["id"]})
        conn.execute(sa.text("DELETE FROM foods WHERE id = :dup"), {"dup": row["id"]})


def upgrade() -> None:
    op.create_table('food_overrides',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('food_id', sa.Integer(), nullable=False),
    sa.Column('kcal', sa.Float(), nullable=False),
    sa.Column('protein', sa.Float(), nullable=False),
    sa.Column('fat', sa.Float(), nullable=False),
    sa.Column('carbs', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['food_id'], ['foods.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'food_id')
    )
    op.create_index(op.f('ix_food_overrides_food_id'), 'food_overrides', ['food_id'], unique=False)

    # A contributor leaving must not take shared foods with them: CASCADE -> SET NULL.
    op.drop_index('ix_foods_owner_id', table_name='foods')
    op.drop_constraint('foods_owner_id_fkey', 'foods', type_='foreignkey')
    op.alter_column('foods', 'owner_id', new_column_name='created_by_id')
    op.create_foreign_key('foods_created_by_id_fkey', 'foods', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_foods_created_by_id'), 'foods', ['created_by_id'], unique=False)

    _merge_duplicate_names(op.get_bind())
    op.create_index('uq_foods_name_lower', 'foods', [sa.text('lower(name)')], unique=True)


def downgrade() -> None:
    op.drop_index('uq_foods_name_lower', table_name='foods')
    op.drop_index(op.f('ix_foods_created_by_id'), table_name='foods')
    op.drop_constraint('foods_created_by_id_fkey', 'foods', type_='foreignkey')
    op.alter_column('foods', 'created_by_id', new_column_name='owner_id')
    op.create_foreign_key('foods_owner_id_fkey', 'foods', 'users', ['owner_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_foods_owner_id', 'foods', ['owner_id'], unique=False)
    op.drop_index(op.f('ix_food_overrides_food_id'), table_name='food_overrides')
    op.drop_table('food_overrides')
