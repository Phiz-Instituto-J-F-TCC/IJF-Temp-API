from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.schemas import (
    ProfessorMateriaResponse,
    AlunoResumoProfessor,
    RelatorioProfessorMateria,
    ProfessorAlunoResponse,
    NotaDetalhe,
    AulaPresenca,
    RelatorioProfessorAluno,
    CoordenadorSalaResponse,
    MateriaSalaResumo,
    CoordenadorAlunoGeralResponse,
    MateriaNotas,
    RelatorioNotas,
    RelatorioPresenca,
)

router = APIRouter(prefix="/coordenador", tags=["Coordenador"])


# ============================
# Helpers
# ============================

async def _buscar_coordenador(conn, numero_phiz: str):
    """Busca coordenador ativo pelo numero_phiz."""
    cur = await conn.execute(
        'SELECT "id", "nome" FROM "Coordenador" WHERE "numero_phiz" = %s AND "ativo" = TRUE',
        (numero_phiz,),
    )
    coordenador = await cur.fetchone()
    if not coordenador:
        raise HTTPException(status_code=404, detail="Coordenador não encontrado ou inativo.")
    return coordenador


async def _buscar_sala_materia(conn, sala_str: str, materia_nome: str) -> dict:
    """
    Busca e retorna a Sala_Materia correspondente ao formato de sala (ex: '2A') e matéria (LIKE case-insensitive e accent-insensitive).
    """
    import re
    import unicodedata

    def remover_acentos(texto: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")

    match = re.match(r"^(\d+)([a-zA-Z])$", sala_str.strip())
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Formato de sala inválido. Use o formato 'AnoLetra', ex: '2A', '3B', '1C'."
        )
    ano_str, letra = match.groups()
    ano = int(ano_str)
    letra = letra.upper()

    # Buscar a sala
    cur = await conn.execute(
        'SELECT "id" FROM "Sala" WHERE "ano" = %s AND UPPER("letra") = %s',
        (ano, letra),
    )
    sala = await cur.fetchone()
    if not sala:
        raise HTTPException(
            status_code=404,
            detail=f"Sala '{sala_str}' não encontrada."
        )

    # Buscar a matéria ignorando acentuações e case-sensitivity usando a função unaccent() do PG
    cur = await conn.execute(
        'SELECT "id", "nome" FROM "Materia" WHERE unaccent("nome") ILIKE unaccent(%s)',
        (f"%{materia_nome.strip()}%",),
    )
    materias = await cur.fetchall()
    if not materias:
        raise HTTPException(
            status_code=404,
            detail=f"Matéria '{materia_nome}' não encontrada."
        )
    
    # Priorizar correspondência exata sem acentos para evitar ambiguidades se existirem
    materia = None
    materia_nome_norm = remover_acentos(materia_nome.strip().upper())
    for m in materias:
        if remover_acentos(m["nome"].strip().upper()) == materia_nome_norm:
            materia = m
            break
    if not materia:
        materia = materias[0]

    # Buscar a Sala_Materia
    cur = await conn.execute(
        'SELECT "id" FROM "Sala_Materia" WHERE "id_sala" = %s AND "id_materia" = %s',
        (sala["id"], materia["id"]),
    )
    sm = await cur.fetchone()
    if not sm:
        raise HTTPException(
            status_code=404,
            detail=f"A matéria '{materia['nome']}' não é lecionada na sala '{sala_str}'."
        )

    return {
        "id_sala_materia": sm["id"],
        "id_sala": sala["id"],
        "id_materia": materia["id"],
        "materia_nome": materia["nome"],
        "ano": ano,
        "letra": letra,
    }


async def _calcular_media_aluno_na_materia(conn, id_aluno: int, id_sala_materia: int) -> float | None:
    cur = await conn.execute(
        """
        SELECT n."valor", a."peso_nota"
        FROM "Nota" n
        JOIN "Avaliacao" a ON a."id" = n."id_avaliacao"
        WHERE n."id_aluno" = %s AND a."id_sala_materia" = %s
        """,
        (id_aluno, id_sala_materia),
    )
    notas = await cur.fetchall()
    if not notas:
        return None
    soma_ponderada = sum(float(r["valor"]) * float(r["peso_nota"]) for r in notas)
    soma_pesos = sum(float(r["peso_nota"]) for r in notas)
    if soma_pesos == 0:
        return 0.0
    return round(soma_ponderada / soma_pesos, 2)


async def _calcular_presenca_aluno_na_materia(conn, id_aluno: int, id_sala_materia: int) -> float | None:
    cur = await conn.execute(
        'SELECT COUNT(*) AS cnt FROM "Aula" WHERE "id_sala_materia" = %s',
        (id_sala_materia,),
    )
    row = await cur.fetchone()
    total_aulas = row["cnt"]
    if total_aulas == 0:
        return None

    cur = await conn.execute(
        """
        SELECT COUNT(*) AS cnt FROM "Presenca" p
        JOIN "Aula" au ON au."id" = p."id_aula"
        WHERE p."id_aluno" = %s AND au."id_sala_materia" = %s
        """,
        (id_aluno, id_sala_materia),
    )
    row = await cur.fetchone()
    presencas = row["cnt"]
    return round((presencas / total_aulas) * 100, 2)


# ============================
# GET /coordenador/materia
# (Mesmo que professor/materia mas SEM verificação de vínculo)
# ============================

@router.get("/materia", response_model=ProfessorMateriaResponse)
async def coordenador_materia(numero_phiz: str, sala: str, materia: str):
    """
    Relatório geral de uma turma em uma matéria. Sem verificação de vínculo.
    """
    pool = await get_connection()

    async with pool.connection() as conn:
        coordenador = await _buscar_coordenador(conn, numero_phiz)
        info = await _buscar_sala_materia(conn, sala, materia)
        id_sala_materia = info["id_sala_materia"]

        # Buscar professor da matéria para o campo "professor" na resposta
        cur = await conn.execute(
            """
            SELECT p."nome"
            FROM "Professor" p
            JOIN "Professor_Sala_Materia" psm ON psm."id_professor" = p."id"
            WHERE psm."id_sala_materia" = %s AND psm."ativo" = TRUE
            LIMIT 1
            """,
            (id_sala_materia,),
        )
        prof_row = await cur.fetchone()
        professor_nome = prof_row["nome"] if prof_row else "Sem professor atribuído"

        cur = await conn.execute(
            """
            SELECT al."id", al."nome", al."numero_phiz"
            FROM "Aluno" al
            JOIN "Aluno_Sala" als ON als."id_aluno" = al."id"
            WHERE als."id_sala" = %s AND als."atual" = TRUE
            ORDER BY al."nome"
            """,
            (info["id_sala"],),
        )
        alunos = await cur.fetchall()

        alunos_list = []
        medias = []
        presencas = []

        for al in alunos:
            media = await _calcular_media_aluno_na_materia(conn, al["id"], id_sala_materia)
            pres = await _calcular_presenca_aluno_na_materia(conn, al["id"], id_sala_materia)

            alunos_list.append(
                AlunoResumoProfessor(
                    nome=al["nome"],
                    numero_phiz=al["numero_phiz"],
                    media=media,
                    porcentagem_presenca=pres,
                )
            )
            if media is not None:
                medias.append(media)
            if pres is not None:
                presencas.append(pres)

        media_turma = round(sum(medias) / len(medias), 2) if medias else None
        presenca_turma = round(sum(presencas) / len(presencas), 2) if presencas else None

        acima = sum(1 for m in medias if m >= (media_turma or 0)) if media_turma else 0
        abaixo = sum(1 for m in medias if m < (media_turma or 0)) if media_turma else 0

        return ProfessorMateriaResponse(
            professor=professor_nome,
            materia=info["materia_nome"],
            sala=f'{info["ano"]}{info["letra"]}',
            alunos=alunos_list,
            relatorio=RelatorioProfessorMateria(
                media_turma=media_turma,
                nota_mais_alta=max(medias) if medias else None,
                nota_mais_baixa=min(medias) if medias else None,
                alunos_acima_media=acima,
                alunos_abaixo_media=abaixo,
                porcentagem_presenca_turma=presenca_turma,
            ),
        )


# ============================
# GET /coordenador/aluno
# (Mesmo que professor/aluno mas SEM verificação de vínculo)
# ============================

@router.get("/aluno", response_model=ProfessorAlunoResponse)
async def coordenador_aluno(numero_phiz: str, sala: str, materia: str, numero_phiz_aluno: str):
    """
    Relatório detalhado de um aluno em uma matéria. Sem verificação de vínculo.
    """
    pool = await get_connection()

    async with pool.connection() as conn:
        coordenador = await _buscar_coordenador(conn, numero_phiz)
        info = await _buscar_sala_materia(conn, sala, materia)
        id_sala_materia = info["id_sala_materia"]

        cur = await conn.execute(
            'SELECT "id", "nome" FROM "Aluno" WHERE "numero_phiz" = %s',
            (numero_phiz_aluno,),
        )
        aluno = await cur.fetchone()
        if not aluno:
            raise HTTPException(status_code=404, detail="Aluno não encontrado.")

        # Validar que o aluno pertence à sala e está ativo (atual = TRUE)
        cur = await conn.execute(
            """
            SELECT 1 FROM "Aluno_Sala"
            WHERE "id_aluno" = %s AND "id_sala" = %s AND "atual" = TRUE
            """,
            (aluno["id"], info["id_sala"]),
        )
        vinculo_aluno = await cur.fetchone()
        if not vinculo_aluno:
            raise HTTPException(status_code=403, detail="Aluno não pertence ou não está ativo nesta sala.")

        # Notas
        cur = await conn.execute(
            """
            SELECT n."valor", a."nome" AS avaliacao_nome, a."periodo", a."peso_nota"
            FROM "Nota" n
            JOIN "Avaliacao" a ON a."id" = n."id_avaliacao"
            WHERE n."id_aluno" = %s AND a."id_sala_materia" = %s
            ORDER BY a."periodo", a."nome"
            """,
            (aluno["id"], id_sala_materia),
        )
        notas_rows = await cur.fetchall()
        notas_list = [
            NotaDetalhe(
                avaliacao=r["avaliacao_nome"],
                periodo=r["periodo"],
                valor=float(r["valor"]),
                peso=float(r["peso_nota"]),
            )
            for r in notas_rows
        ]

        # Presenças
        cur = await conn.execute(
            'SELECT "id" AS id_aula FROM "Aula" WHERE "id_sala_materia" = %s ORDER BY "id"',
            (id_sala_materia,),
        )
        aulas = await cur.fetchall()

        cur = await conn.execute(
            """
            SELECT p."id_aula"
            FROM "Presenca" p
            JOIN "Aula" au ON au."id" = p."id_aula"
            WHERE p."id_aluno" = %s AND au."id_sala_materia" = %s
            """,
            (aluno["id"], id_sala_materia),
        )
        presencas = await cur.fetchall()
        presencas_set = {r["id_aula"] for r in presencas}

        presencas_list = [
            AulaPresenca(
                id_aula=au["id_aula"],
                materia=info["materia_nome"],
                presente=au["id_aula"] in presencas_set,
            )
            for au in aulas
        ]

        media_aluno = await _calcular_media_aluno_na_materia(conn, aluno["id"], id_sala_materia)

        # Média da turma
        cur = await conn.execute(
            'SELECT "id_aluno" FROM "Aluno_Sala" WHERE "id_sala" = %s AND "atual" = TRUE',
            (info["id_sala"],),
        )
        alunos_sala = await cur.fetchall()
        medias_turma = []
        for al in alunos_sala:
            m = await _calcular_media_aluno_na_materia(conn, al["id_aluno"], id_sala_materia)
            if m is not None:
                medias_turma.append(m)
        media_turma = round(sum(medias_turma) / len(medias_turma), 2) if medias_turma else None

        total_aulas = len(aulas)
        pres_pct = round((len(presencas_set) / total_aulas) * 100, 2) if total_aulas > 0 else None

        # Buscar professor responsável
        cur = await conn.execute(
            """
            SELECT p."nome"
            FROM "Professor" p
            JOIN "Professor_Sala_Materia" psm ON psm."id_professor" = p."id"
            WHERE psm."id_sala_materia" = %s AND psm."ativo" = TRUE
            LIMIT 1
            """,
            (id_sala_materia,),
        )
        prof_row = await cur.fetchone()
        professor_nome = prof_row["nome"] if prof_row else "Sem professor"

        return ProfessorAlunoResponse(
            professor=professor_nome,
            aluno=aluno["nome"],
            materia=info["materia_nome"],
            sala=f'{info["ano"]}{info["letra"]}',
            notas=notas_list,
            presencas=presencas_list,
            relatorio=RelatorioProfessorAluno(
                media_aluno=media_aluno,
                media_turma=media_turma,
                porcentagem_presenca=pres_pct,
            ),
        )


# ============================
# GET /coordenador/sala
# ============================

@router.get("/sala", response_model=CoordenadorSalaResponse)
async def coordenador_sala(numero_phiz: str, id_sala: int):
    """
    Visão geral de uma sala com todas as matérias.
    """
    pool = await get_connection()

    async with pool.connection() as conn:
        coordenador = await _buscar_coordenador(conn, numero_phiz)

        cur = await conn.execute(
            'SELECT "id", "ano", "letra" FROM "Sala" WHERE "id" = %s',
            (id_sala,),
        )
        sala = await cur.fetchone()
        if not sala:
            raise HTTPException(status_code=404, detail="Sala não encontrada.")

        # Buscar matérias da sala
        cur = await conn.execute(
            """
            SELECT sm."id" AS id_sala_materia, m."nome" AS materia_nome
            FROM "Sala_Materia" sm
            JOIN "Materia" m ON m."id" = sm."id_materia"
            WHERE sm."id_sala" = %s
            ORDER BY m."nome"
            """,
            (id_sala,),
        )
        sala_materias = await cur.fetchall()

        # Alunos da sala
        cur = await conn.execute(
            """
            SELECT als."id_aluno"
            FROM "Aluno_Sala" als
            WHERE als."id_sala" = %s AND als."atual" = TRUE
            """,
            (id_sala,),
        )
        alunos = await cur.fetchall()

        materias_list = []
        for sm in sala_materias:
            medias = []
            presencas = []
            for al in alunos:
                media = await _calcular_media_aluno_na_materia(conn, al["id_aluno"], sm["id_sala_materia"])
                pres = await _calcular_presenca_aluno_na_materia(conn, al["id_aluno"], sm["id_sala_materia"])
                if media is not None:
                    medias.append(media)
                if pres is not None:
                    presencas.append(pres)

            materias_list.append(
                MateriaSalaResumo(
                    materia=sm["materia_nome"],
                    id_sala_materia=sm["id_sala_materia"],
                    media_turma=round(sum(medias) / len(medias), 2) if medias else None,
                    porcentagem_presenca=round(sum(presencas) / len(presencas), 2) if presencas else None,
                )
            )

        return CoordenadorSalaResponse(
            coordenador=coordenador["nome"],
            sala=f'{sala["ano"]}{sala["letra"]}',
            materias=materias_list,
        )


# ============================
# GET /coordenador/aluno/geral
# ============================

@router.get("/aluno/geral", response_model=CoordenadorAlunoGeralResponse)
async def coordenador_aluno_geral(numero_phiz: str, numero_phiz_aluno: str):
    """
    Visão geral completa de um aluno: todas matérias, notas e presença.
    """
    pool = await get_connection()

    async with pool.connection() as conn:
        coordenador = await _buscar_coordenador(conn, numero_phiz)

        cur = await conn.execute(
            'SELECT "id", "nome" FROM "Aluno" WHERE "numero_phiz" = %s',
            (numero_phiz_aluno,),
        )
        aluno = await cur.fetchone()
        if not aluno:
            raise HTTPException(status_code=404, detail="Aluno não encontrado.")

        # Sala atual
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
            raise HTTPException(status_code=404, detail="Aluno não possui sala atual.")

        # Matérias da sala
        cur = await conn.execute(
            """
            SELECT sm."id" AS id_sala_materia, m."nome" AS materia_nome
            FROM "Sala_Materia" sm
            JOIN "Materia" m ON m."id" = sm."id_materia"
            WHERE sm."id_sala" = %s
            ORDER BY m."nome"
            """,
            (sala_row["id"],),
        )
        sala_materias = await cur.fetchall()

        # Notas por matéria
        materias_list = []
        todas_medias = []
        medias_por_materia = []

        # Presença geral
        total_aulas_geral = 0
        total_presencas_geral = 0

        for sm in sala_materias:
            # Notas
            cur = await conn.execute(
                """
                SELECT n."valor", a."nome" AS avaliacao_nome, a."periodo", a."peso_nota"
                FROM "Nota" n
                JOIN "Avaliacao" a ON a."id" = n."id_avaliacao"
                WHERE n."id_aluno" = %s AND a."id_sala_materia" = %s
                ORDER BY a."periodo", a."nome"
                """,
                (aluno["id"], sm["id_sala_materia"]),
            )
            notas_rows = await cur.fetchall()

            notas_list = [
                NotaDetalhe(
                    avaliacao=r["avaliacao_nome"],
                    periodo=r["periodo"],
                    valor=float(r["valor"]),
                    peso=float(r["peso_nota"]),
                )
                for r in notas_rows
            ]

            media = await _calcular_media_aluno_na_materia(conn, aluno["id"], sm["id_sala_materia"])

            materias_list.append(
                MateriaNotas(
                    materia=sm["materia_nome"],
                    sala=f'{sala_row["ano"]}{sala_row["letra"]}',
                    notas=notas_list,
                    media_ponderada=media if media is not None else 0.0,
                )
            )

            medias_por_materia.append({
                "materia": sm["materia_nome"],
                "sala": f'{sala_row["ano"]}{sala_row["letra"]}',
                "media": media,
            })
            if media is not None:
                todas_medias.append(media)

            # Presença por matéria
            cur = await conn.execute(
                'SELECT COUNT(*) AS cnt FROM "Aula" WHERE "id_sala_materia" = %s',
                (sm["id_sala_materia"],),
            )
            row = await cur.fetchone()
            aulas_materia = row["cnt"]

            cur = await conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM "Presenca" p
                JOIN "Aula" au ON au."id" = p."id_aula"
                WHERE p."id_aluno" = %s AND au."id_sala_materia" = %s
                """,
                (aluno["id"], sm["id_sala_materia"]),
            )
            row = await cur.fetchone()
            presencas_materia = row["cnt"]

            total_aulas_geral += aulas_materia
            total_presencas_geral += presencas_materia

        media_geral = round(sum(todas_medias) / len(todas_medias), 2) if todas_medias else 0.0
        total_faltas_geral = total_aulas_geral - total_presencas_geral
        pct_presenca = round((total_presencas_geral / total_aulas_geral) * 100, 2) if total_aulas_geral > 0 else 0.0

        return CoordenadorAlunoGeralResponse(
            coordenador=coordenador["nome"],
            aluno=aluno["nome"],
            sala=f'{sala_row["ano"]}{sala_row["letra"]}',
            materias=materias_list,
            presenca_geral=RelatorioPresenca(
                total_aulas=total_aulas_geral,
                total_presencas=total_presencas_geral,
                total_faltas=total_faltas_geral,
                porcentagem_presenca=pct_presenca,
            ),
            relatorio=RelatorioNotas(
                media_geral=media_geral,
                medias_por_materia=medias_por_materia,
            ),
        )
