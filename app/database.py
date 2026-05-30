import os
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

pool: AsyncConnectionPool | None = None


async def create_pool():
    """Cria o pool de conexões com o NeonDB."""
    global pool
    pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        min_size=2,
        max_size=10,
        kwargs={"row_factory": dict_row},
    )
    await pool.open()


async def close_pool():
    """Fecha o pool de conexões."""
    global pool
    if pool:
        await pool.close()
        pool = None


async def get_connection():
    """Retorna o pool de conexões."""
    return pool
