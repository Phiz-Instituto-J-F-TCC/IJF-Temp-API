from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.schemas import LinkarPhizRequest, LinkarPhizResponse

router = APIRouter(tags=["Link PhizNumber"])


@router.post("/linkar-phiz", response_model=LinkarPhizResponse)
async def linkar_phiz(data: LinkarPhizRequest):
    """
    Recebe email corporativo e número de telefone.
    Verifica se pertence a um Coordenador, Professor ou Aluno
    e atualiza o numero_phiz na tabela correspondente.
    """
    pool = await get_connection()

    # Ordem de verificação: Coordenador → Professor → Aluno
    tabelas = [
        ("Coordenador", "coordenador"),
        ("Professor", "professor"),
        ("Aluno", "aluno"),
    ]

    async with pool.connection() as conn:
        for tabela, tipo in tabelas:
            cur = await conn.execute(
                f'SELECT "id", "nome" FROM "{tabela}" WHERE "email" = %s',
                (data.email,),
            )
            row = await cur.fetchone()
            if row:
                await conn.execute(
                    f'UPDATE "{tabela}" SET "numero_phiz" = %s WHERE "id" = %s',
                    (data.numero_phiz, row["id"]),
                )
                return LinkarPhizResponse(
                    mensagem=f"Número PhizLink vinculado com sucesso ao {tipo}.",
                    tipo=tipo,
                    nome=row["nome"],
                )

    raise HTTPException(
        status_code=404,
        detail="Email não encontrado em nenhuma tabela (Coordenador, Professor ou Aluno).",
    )
