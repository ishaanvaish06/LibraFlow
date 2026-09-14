"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-14
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('books',
        sa.Column('isbn',        sa.String(64),        nullable=False,        primary_key=True,    ),
        sa.Column('title',        sa.String(512),        nullable=False,    ),
        sa.Column('authors',        postgresql.JSONB(),        nullable=False,    ),
        sa.Column('category',        sa.String(128),        nullable=False,    ),
        sa.Column('publication_year',        sa.Integer(),        nullable=False,    ),
        sa.Column('publisher',        sa.String(256),        nullable=False,    ),
        sa.Column('description',        sa.Text(),        nullable=False,    ),
        sa.Column('rating',        sa.Float(),        nullable=False,    ),
        sa.Column('difficulty_level',        sa.String(64),        nullable=False,    ),
        sa.Column('keywords',        postgresql.JSONB(),        nullable=False,    ),
        sa.Column('borrow_history_count',        sa.Integer(),        nullable=False,    ),
        sa.Column('created_at',        sa.DateTime(),        nullable=False,    ),
        sa.Column('format',        sa.String(16),        nullable=False,    ),
        sa.Column('weight_grams',        sa.Integer(),        nullable=True,    ),
        sa.Column('page_count',        sa.Integer(),        nullable=True,    ),
        sa.Column('download_url',        sa.String(512),        nullable=True,    ),
        sa.Column('file_size_mb',        sa.Float(),        nullable=True,    ),
        sa.Column('file_format',        sa.String(16),        nullable=True,    ),
        sa.Column('drm_protected',        sa.Boolean(),        nullable=True,    ),
        sa.Column('max_concurrent_downloads',        sa.Integer(),        nullable=True,    ),
        sa.Column('active_readers_count',        sa.Integer(),        nullable=True,    ),
        sa.Column('stream_url',        sa.String(512),        nullable=True,    ),
        sa.Column('duration_minutes',        sa.Integer(),        nullable=True,    ),
        sa.Column('narrator',        sa.String(256),        nullable=True,    ),
    )
    
    op.create_table('circulation_records',
        sa.Column('id',        sa.Integer(),        nullable=False,        primary_key=True,    ),
        sa.Column('transaction_id',        sa.String(64),        nullable=False,    ),
        sa.Column('type',        sa.String(32),        nullable=False,    ),
        sa.Column('copy_id',        sa.String(64),        nullable=False,    ),
        sa.Column('isbn',        sa.String(64),        nullable=False,    ),
        sa.Column('user_id',        sa.String(64),        nullable=False,    ),
        sa.Column('borrowed_at',        sa.String(64),        nullable=True,    ),
        sa.Column('due_date',        sa.String(64),        nullable=True,    ),
        sa.Column('returned_at',        sa.String(64),        nullable=True,    ),
        sa.Column('is_late',        sa.Boolean(),        nullable=False,    ),
        sa.Column('is_damaged',        sa.Boolean(),        nullable=False,    ),
        sa.Column('created_at',        sa.DateTime(),        nullable=False,    ),
    )
    
    op.create_table('library_branches',
        sa.Column('branch_id',        sa.String(64),        nullable=False,        primary_key=True,    ),
        sa.Column('name',        sa.String(256),        nullable=False,    ),
        sa.Column('city',        sa.String(128),        nullable=False,    ),
        sa.Column('address',        sa.String(512),        nullable=False,    ),
        sa.Column('phone',        sa.String(64),        nullable=False,    ),
        sa.Column('latitude',        sa.Float(),        nullable=False,    ),
        sa.Column('longitude',        sa.Float(),        nullable=False,    ),
    )
    
    op.create_table('book_copies',
        sa.Column('copy_id',        sa.String(64),        nullable=False,        primary_key=True,    ),
        sa.Column('book_isbn',        sa.String(64),        nullable=False,    ),
        sa.Column('branch_id',        sa.String(64),        nullable=False,    ),
        sa.Column('shelf_location',        sa.String(64),        nullable=False,    ),
        sa.Column('price',        sa.Float(),        nullable=False,    ),
        sa.Column('status',        sa.String(32),        nullable=False,    ),
        sa.Column('current_borrower_id',        sa.String(64),        nullable=True,    ),
        sa.Column('current_reserver_id',        sa.String(64),        nullable=True,    ),
        sa.Column('target_branch_id',        sa.String(64),        nullable=True,    ),
        sa.Column('borrow_count',        sa.Integer(),        nullable=False,    ),
        sa.Column('version',        sa.Integer(),        nullable=False,    ),
        sa.Column('created_at',        sa.DateTime(),        nullable=False,    ),
        sa.ForeignKeyConstraint(['book_isbn'], ['books.isbn'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['library_branches.branch_id']),
    )
    
    op.create_table('users',
        sa.Column('user_id',        sa.String(64),        nullable=False,        primary_key=True,    ),
        sa.Column('name',        sa.String(256),        nullable=False,    ),
        sa.Column('email',        sa.String(256),        nullable=False,    ),
        sa.Column('password_hash',        sa.String(256),        nullable=False,    ),
        sa.Column('role',        sa.String(32),        nullable=False,    ),
        sa.Column('max_borrow_limit',        sa.Integer(),        nullable=False,    ),
        sa.Column('branch_id',        sa.String(64),        nullable=True,    ),
        sa.Column('active_borrowed_copy_ids',        postgresql.JSONB(),        nullable=False,    ),
        sa.Column('borrow_history',        postgresql.JSONB(),        nullable=False,    ),
        sa.Column('active_reservations',        postgresql.JSONB(),        nullable=False,    ),
        sa.Column('unpaid_fines_balance',        sa.Float(),        nullable=False,    ),
        sa.Column('security_deposit_balance',        sa.Float(),        nullable=False,    ),
        sa.Column('is_suspended',        sa.Boolean(),        nullable=False,    ),
        sa.Column('created_at',        sa.DateTime(),        nullable=False,    ),
        sa.Column('academic_year',        sa.Integer(),        nullable=True,    ),
        sa.Column('major',        sa.String(128),        nullable=True,    ),
        sa.Column('exam_date',        sa.String(32),        nullable=True,    ),
        sa.Column('department',        sa.String(256),        nullable=True,    ),
        sa.Column('staff_code',        sa.String(64),        nullable=True,    ),
        sa.ForeignKeyConstraint(['branch_id'], ['library_branches.branch_id']),
    )
    

def downgrade() -> None:
    op.drop_table('users')
    op.drop_table('book_copies')
    op.drop_table('library_branches')
    op.drop_table('circulation_records')
    op.drop_table('books')
