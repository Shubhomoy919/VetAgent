"""Initial schema: runs, results, traces, answer cache, reviews, cases, drug rows, SVTG passages, settings,
rate limits, access-code lockout and daily token budget.

Revision ID: 0001
Revises:
Create Date: 2026-10-19 19:54:16.687534
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('app_settings',
    sa.Column('key', sa.String(length=40), nullable=False),
    sa.Column('value', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('auth_failures',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=False),
    sa.Column('ts', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('auth_failures', schema=None) as batch_op:
        batch_op.create_index('auth_failures_ip_ts', ['ip', 'ts'], unique=False)

    op.create_table('auth_lockouts',
    sa.Column('ip', sa.String(length=64), nullable=False),
    sa.Column('locked_until', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('ip')
    )
    op.create_table('budget_usage',
    sa.Column('day', sa.String(length=10), nullable=False),
    sa.Column('tokens', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('day')
    )
    op.create_table('cache',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('condition', sa.String(length=4), nullable=False),
    sa.Column('case_id', sa.String(length=40), nullable=False),
    sa.Column('prompt_version', sa.String(length=20), nullable=False),
    sa.Column('interview', sa.Boolean(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.String(length=40), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('cases',
    sa.Column('case_id', sa.String(length=40), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.String(length=40), nullable=False),
    sa.PrimaryKeyConstraint('case_id')
    )
    op.create_table('drug_rows',
    sa.Column('key', sa.String(length=160), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.String(length=40), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('meta',
    sa.Column('key', sa.String(length=40), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('rate_limits',
    sa.Column('ip', sa.String(length=64), nullable=False),
    sa.Column('minute', sa.Integer(), nullable=False),
    sa.Column('hits', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('ip', 'minute')
    )
    op.create_table('runs',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.String(length=40), nullable=False),
    sa.Column('updated_at', sa.String(length=40), nullable=True),
    sa.Column('label', sa.String(length=80), server_default='', nullable=False),
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('prompt_version', sa.String(length=20), nullable=False),
    sa.Column('conditions', sa.JSON(), nullable=False),
    sa.Column('case_ids', sa.JSON(), nullable=False),
    sa.Column('interview', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('force', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='running', nullable=False),
    sa.Column('n_total', sa.Integer(), nullable=False),
    sa.Column('n_done', sa.Integer(), server_default='0', nullable=False),
    sa.Column('finished_at', sa.String(length=40), nullable=True),
    sa.Column('temperature', sa.Float(), nullable=True),
    sa.Column('benchmark_version', sa.String(length=40), nullable=True),
    sa.Column('benchmark_hash', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('svtg_chunks',
    sa.Column('chunk_id', sa.String(length=40), nullable=False),
    sa.Column('ord', sa.Integer(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('printed_page', sa.Integer(), nullable=True),
    sa.Column('section', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('chunk_id')
    )
    with op.batch_alter_table('svtg_chunks', schema=None) as batch_op:
        batch_op.create_index('svtg_chunks_page', ['page'], unique=False)

    op.create_table('results',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('case_id', sa.String(length=40), nullable=False),
    sa.Column('condition', sa.String(length=4), nullable=False),
    sa.Column('interview', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('answer', sa.JSON(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('rules_fired', sa.JSON(), nullable=False),
    sa.Column('owner_questions', sa.JSON(), nullable=False),
    sa.Column('steps', sa.Integer(), server_default='0', nullable=False),
    sa.Column('tokens_in', sa.Integer(), server_default='0', nullable=False),
    sa.Column('tokens_out', sa.Integer(), server_default='0', nullable=False),
    sa.Column('cost_usd', sa.Float(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), server_default='0', nullable=False),
    sa.Column('cached', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('cache_key', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.create_index('results_case_condition', ['case_id', 'condition'], unique=False)
        batch_op.create_index('results_run', ['run_id'], unique=False)

    op.create_table('reviews',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('result_id', sa.Integer(), nullable=False),
    sa.Column('reviewer', sa.String(length=80), nullable=False),
    sa.Column('rating', sa.String(length=20), nullable=False),
    sa.Column('note', sa.Text(), server_default='', nullable=False),
    sa.Column('created_at', sa.String(length=40), nullable=False),
    sa.Column('updated_at', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['result_id'], ['results.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('result_id', 'reviewer', name='reviews_result_reviewer')
    )
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.create_index('reviews_result', ['result_id'], unique=False)

    op.create_table('traces',
    sa.Column('result_id', sa.Integer(), nullable=False),
    sa.Column('steps', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['result_id'], ['results.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('result_id')
    )


def downgrade() -> None:
    op.drop_table('traces')
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.drop_index('reviews_result')

    op.drop_table('reviews')
    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.drop_index('results_run')
        batch_op.drop_index('results_case_condition')

    op.drop_table('results')
    with op.batch_alter_table('svtg_chunks', schema=None) as batch_op:
        batch_op.drop_index('svtg_chunks_page')

    op.drop_table('svtg_chunks')
    op.drop_table('runs')
    op.drop_table('rate_limits')
    op.drop_table('meta')
    op.drop_table('drug_rows')
    op.drop_table('cases')
    op.drop_table('cache')
    op.drop_table('budget_usage')
    op.drop_table('auth_lockouts')
    with op.batch_alter_table('auth_failures', schema=None) as batch_op:
        batch_op.drop_index('auth_failures_ip_ts')

    op.drop_table('auth_failures')
    op.drop_table('app_settings')
