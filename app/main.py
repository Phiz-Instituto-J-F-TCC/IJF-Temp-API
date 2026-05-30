from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_pool, close_pool
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
