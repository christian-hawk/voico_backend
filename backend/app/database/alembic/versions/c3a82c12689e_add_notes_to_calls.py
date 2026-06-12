"""add notes to calls

Revision ID: c3a82c12689e
Revises: 0001
Create Date: 2026-06-11 07:37:39.669458

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a82c12689e"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calls", sa.Column("notes", sqlmodel.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column("calls", "notes")
