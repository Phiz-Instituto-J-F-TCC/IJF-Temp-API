from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_pool, close_pool, get_connection
from app.routers import link, aluno, professor, coordenador


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida do pool de conexões."""
    await create_pool()
    yield
    await close_pool()


app = FastAPI(
    title="PhizLink API",
    description="API para consulta de dados acadêmicos do Instituto J.F. via número PhizLink.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permitir todas as origens (ajustar conforme necessário)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(link.router)
app.include_router(aluno.router)
app.include_router(professor.router)
app.include_router(coordenador.router)


@app.get("/", tags=["Root"])
async def root():
    return {"mensagem": "PhizLink API está rodando.", "docs": "/docs"}


@app.get("/tipo-usuario/{numero_phiz}", tags=["Geral"])
async def verificar_tipo_usuario(numero_phiz: str):
    """
    Retorna a qual tipo de usuário (aluno, professor ou coordenador) um número do Phiz pertence.
    """
    numero_phiz = numero_phiz.replace("%2B", "+")
    
    pool = await get_connection()
    if pool is None:
        raise HTTPException(status_code=500, detail="Pool de conexões não inicializado.")

    # Ordem de verificação: Coordenador → Professor → Aluno
    tabelas = [
        ("Coordenador", "coordenador"),
        ("Professor", "professor"),
        ("Aluno", "aluno"),
    ]

    async with pool.connection() as conn:
        for tabela, tipo in tabelas:
            cur = await conn.execute(
                f'SELECT 1 FROM "{tabela}" WHERE "numero_phiz" = %s',
                (numero_phiz,),
            )
            if await cur.fetchone():
                return {"tipo": tipo}

    raise HTTPException(status_code=404, detail="Número não pertence a nenhum usuário.")
