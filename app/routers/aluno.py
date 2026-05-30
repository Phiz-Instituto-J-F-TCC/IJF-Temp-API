from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.schemas import (
    AlunoNotasResponse,
    MateriaNotas,
    NotaDetalhe,
    RelatorioNotas,
    AlunoPresencaResponse,
    AulaPresenca,
    RelatorioPresenca,
)

router = APIRouter(prefix="/aluno", tags=["Aluno"])


# ============================
# Helpers
# ============================

async def _buscar_aluno(conn, numero_phiz: str):
    """Busca um aluno pelo numero_phiz. Levanta 404 se não encontrar."""
    cur = await conn.execute(
        'SELECT "id", "nome" FROM "Aluno" WHERE "numero_phiz" = %s',
        (numero_phiz,),
    )
    aluno = await cur.fetchone()
    if not aluno:
        raise HTTPException(status_code=404, detail="Aluno não encontrado com esse número PhizLink.")
    return aluno


def _calcular_media_ponderada(notas_rows) -> float | None:
    """Calcula média ponderada a partir de rows com 'valor' e 'peso_nota'."""
    if not notas_rows:
        return None
    soma_ponderada = sum(float(r["valor"]) * float(r["peso_nota"]) for r in notas_rows)
    soma_pesos = sum(float(r["peso_nota"]) for r in notas_rows)
    if soma_pesos == 0:
        return 0.0
    return round(soma_ponderada / soma_pesos, 2)


# ============================
# GET /aluno/notas
# ============================

@router.get("/notas", response_model=AlunoNotasResponse)
async def aluno_notas(numero_phiz: str):
    """
    Retorna todas as notas de um aluno na sua sala atual agrupadas por matéria,
    com relatório contendo média geral e média por matéria.
    """
    pool = await get_connection()

    async with pool.connection() as conn:
        aluno = await _buscar_aluno(conn, numero_phiz)

        # Buscar sala atual do aluno
        cur = await conn.execute(
            """
            SELECT s."id"
            FROM "Aluno_Sala" als
            JOIN "Sala" s ON s."id" = als."id_sala"
            WHERE als."id_aluno" = %s AND als."atual" = TRUE
            """,
            (aluno["id"],),
        )
        sala_row = await cur.fetchone()
        if not sala_row:
            raise HTTPException(status_code=404, detail="Aluno não possui sala atual cadastrada.")

        # Buscar todas as notas com JOINs, limitadas à sala atual do aluno
        cur = await conn.execute(
            """
            SELECT
                n."valor",
                a."nome"       AS avaliacao_nome,
                a."periodo",
                a."peso_nota",
                m."nome"       AS materia_nome,
                s."ano",
                s."letra",
                sm."id"        AS id_sala_materia
            FROM "Nota" n
            JOIN "Avaliacao" a      ON a."id" = n."id_avaliacao"
            JOIN "Sala_Materia" sm  ON sm."id" = a."id_sala_materia"
            JOIN "Materia" m        ON m."id" = sm."id_materia"
            JOIN "Sala" s           ON s."id" = sm."id_sala"
            WHERE n."id_aluno" = %s AND sm."id_sala" = %s
            ORDER BY m."nome", a."periodo", a."nome"
            """,
            (aluno["id"], sala_row["id"]),
        )
        rows = await cur.fetchall()

        # Agrupar por matéria (id_sala_materia para separar mesma matéria em salas diferentes)
        materias_dict: dict[int, dict] = {}
        for r in rows:
            sm_id = r["id_sala_materia"]
            if sm_id not in materias_dict:
                materias_dict[sm_id] = {
                    "materia": r["materia_nome"],
                    "sala": f'{r["ano"]}{r["letra"]}',
                    "notas_rows": [],
                    "notas": [],
                }
            materias_dict[sm_id]["notas_rows"].append(r)
            materias_dict[sm_id]["notas"].append(
                NotaDetalhe(
                    avaliacao=r["avaliacao_nome"],
                    periodo=r["periodo"],
                    valor=float(r["valor"]),
                    peso=float(r["peso_nota"]),
                )
            )

        # Montar resposta
        materias_list = []
        medias_por_materia = []
        todas_medias = []

        for sm_id, data in materias_dict.items():
            media = _calcular_media_ponderada(data["notas_rows"])
            materias_list.append(
                MateriaNotas(
                    materia=data["materia"],
                    sala=data["sala"],
                    notas=data["notas"],
                    media_ponderada=media if media is not None else 0.0,
                )
            )
            medias_por_materia.append({
                "materia": data["materia"],
                "sala": data["sala"],
                "media": media,
            })
            if media is not None:
                todas_medias.append(media)

        media_geral = round(sum(todas_medias) / len(todas_medias), 2) if todas_medias else 0.0

        return AlunoNotasResponse(
            aluno=aluno["nome"],
            materias=materias_list,
            relatorio=RelatorioNotas(
                media_geral=media_geral,
                medias_por_materia=medias_por_materia,
            ),
        )


# ============================
# GET /aluno/presenca
# ============================

@router.get("/presenca", response_model=AlunoPresencaResponse)
async def aluno_presenca(numero_phiz: str):
    """
    Retorna todas as aulas que o aluno deveria participar,
    quais teve presença e quais faltou, com relatório de porcentagem.
    """
    pool = await get_connection()

    async with pool.connection() as conn:
        aluno = await _buscar_aluno(conn, numero_phiz)

        # Buscar sala atual do aluno
        cur = await conn.execute(
            """
            SELECT s."id", s."ano", s."letra"
            FROM "Aluno_Sala" als
            JOIN "Sala" s ON s."id" = als."id_sala"
            WHERE als."id_aluno" = %s AND als."atual" = TRUE
            """,
            (aluno["id"],),
        )
        sala_row = await cur.fetchone()
        if not sala_row:
            raise HTTPException(status_code=404, detail="Aluno não possui sala atual cadastrada.")

        # Buscar todas as aulas da sala do aluno
        cur = await conn.execute(
            """
            SELECT
                au."id"   AS id_aula,
                m."nome"  AS materia_nome
            FROM "Aula" au
            JOIN "Sala_Materia" sm ON sm."id" = au."id_sala_materia"
            JOIN "Materia" m       ON m."id" = sm."id_materia"
            WHERE sm."id_sala" = %s
            ORDER BY au."id"
            """,
            (sala_row["id"],),
        )
        aulas = await cur.fetchall()

        # Buscar presenças do aluno
        cur = await conn.execute(
            """
            SELECT p."id_aula"
            FROM "Presenca" p
            JOIN "Aula" au         ON au."id" = p."id_aula"
            JOIN "Sala_Materia" sm ON sm."id" = au."id_sala_materia"
            WHERE p."id_aluno" = %s AND sm."id_sala" = %s
            """,
            (aluno["id"], sala_row["id"]),
        )
        presencas = await cur.fetchall()
        presencas_set = {r["id_aula"] for r in presencas}

        # Montar lista de aulas com status
        aulas_list = []
        for aula in aulas:
            aulas_list.append(
                AulaPresenca(
                    id_aula=aula["id_aula"],
                    materia=aula["materia_nome"],
                    presente=aula["id_aula"] in presencas_set,
                )
            )

        total = len(aulas_list)
        total_presencas = len(presencas_set)
        total_faltas = total - total_presencas
        porcentagem = round((total_presencas / total) * 100, 2) if total > 0 else 0.0

        return AlunoPresencaResponse(
            aluno=aluno["nome"],
            sala=f'{sala_row["ano"]}{sala_row["letra"]}',
            aulas=aulas_list,
            relatorio=RelatorioPresenca(
                total_aulas=total,
                total_presencas=total_presencas,
                total_faltas=total_faltas,
                porcentagem_presenca=porcentagem,
            ),
        )
