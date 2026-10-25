"""Cross-platform, data-preserving migration runner. Run from backend/."""
from pathlib import Path
import psycopg
from app.config import get_settings


def migrate():
    settings=get_settings()
    url=settings.database_url.replace('postgresql+psycopg://','postgresql://',1)
    sql_dir=Path(__file__).resolve().parents[2]/'db'
    with psycopg.connect(url,autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(42000)')
            try:
                cursor.execute("SELECT to_regclass('public.contracts')")
                if cursor.fetchone()[0] is None:cursor.execute((sql_dir/'001_initial.sql').read_text())
                for name in ['002_ingestion.sql','003_analytics.sql','004_workbench.sql','005_accounts.sql']:
                    cursor.execute((sql_dir/name).read_text())
            finally:cursor.execute('SELECT pg_advisory_unlock(42000)')
    print('Database migrations applied without deleting existing data.')


if __name__=='__main__':migrate()
