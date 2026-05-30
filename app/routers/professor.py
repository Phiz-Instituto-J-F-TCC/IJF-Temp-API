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
)

router = APIRouter(prefix="/professor", tags=["Professor"])


# ============================
# Helpers
# ============================

async def _buscar_professor(conn, numero_phiz: str):
    """Busca professor pelo numero_phiz."""
    cur = await conn.execute(
        'SELECT "id", "nome" FROM "Professor" WHERE "numero_phiz" = %s',
        (numero_phiz,),
    )
    professor = await cur.fetchone()
    if not professor:
        raise HTTPException(status_code=404, detail="Professor não encontrado com esse número PhizLink.")
    return professor


async def _validar_professor_sala_materia(conn, id_professor: int, id_sala_materia: int):
    """Valida se o professor leciona naquela sala_materia."""
    cur = await conn.execute(
        """
        SELECT 1 FROM "Professor_Sala_Materia"
        WHERE "id_professor" = %s AND "id_sala_materia" = %s AND "ativo" = TRUE
        """,
        (id_professor, id_sala_materia),
    )
    vinculo = await cur.fetchone()
    if not vinculo:
        raise HTTPException(
            status_code=403,
            detail="Professor não leciona essa matéria nessa sala.",
        )


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
    """Calcula média ponderada de um aluno em uma sala_materia."""
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
    """Calcula porcentagem de presença de um aluno em uma sala_materia."""
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
# GET /professor/materia
# ============================

@router.get("/materia", response_model=ProfessorMateriaResponse)
async def professor_materia(numero_phiz: str, sala: str, materia: str):
    """
    Relatório geral de uma turma em uma matéria específica.
    Valida se o professor realmente leciona essa matéria nessa sala.
    """
    pool = await get_connection()

    async with pool.connection() as conn:
        professor = await _buscar_professor(conn, numero_phiz)
        info = await _buscar_sala_materia(conn, sala, materia)
        id_sala_materia = info["id_sala_materia"]

        await _validar_professor_sala_materia(conn, professor["id"], id_sala_materia)

        # Buscar alunos da sala
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

        # Calcular média e presença de cada aluno
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

        media_turma = 7 # Valor fixo da média escolar
        presenca_turma = round(sum(presencas) / len(presencas), 2) if presencas else None

        acima = sum(1 for m in medias if m >= (media_turma or 0)) if media_turma else 0
        abaixo = sum(1 for m in medias if m < (media_turma or 0)) if media_turma else 0

        return ProfessorMateriaResponse(
            professor=professor["nome"],
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
# GET /professor/aluno
# ============================

@router.get("/aluno", response_model=ProfessorAlunoResponse)
async def professor_aluno(numero_phiz: str, sala: str, materia: str, numero_phiz_aluno: str):
    """
    Relatório detalhado de um aluno específico em uma matéria.
    Valida se o professor leciona essa matéria e se o aluno pertence à sala.
    """
    pool = await get_connection()

    async with pool.connection() as conn:
        professor = await _buscar_professor(conn, numero_phiz)
        info = await _buscar_sala_materia(conn, sala, materia)
        id_sala_materia = info["id_sala_materia"]

        await _validar_professor_sala_materia(conn, professor["id"], id_sala_materia)

        # Buscar aluno
        cur = await conn.execute(
            'SELECT "id", "nome" FROM "Aluno" WHERE "numero_phiz" = %s',
            (numero_phiz_aluno,),
        )
        aluno = await cur.fetchone()
        if not aluno:
            raise HTTPException(status_code=404, detail="Aluno não encontrado com esse número PhizLink.")

        # Validar que o aluno pertence à sala
        cur = await conn.execute(
            """
            SELECT 1 FROM "Aluno_Sala"
            WHERE "id_aluno" = %s AND "id_sala" = %s AND "atual" = TRUE
            """,
            (aluno["id"], info["id_sala"]),
        )
        vinculo_aluno = await cur.fetchone()
        if not vinculo_aluno:
            raise HTTPException(status_code=403, detail="Aluno não pertence a essa sala.")

        # Notas detalhadas
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

        # Presenças detalhadas
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

        # Relatório
        media_aluno = await _calcular_media_aluno_na_materia(conn, aluno["id"], id_sala_materia)

        # Média da turma para comparação
        cur = await conn.execute(
            """
            SELECT als."id_aluno"
            FROM "Aluno_Sala" als
            WHERE als."id_sala" = %s AND als."atual" = TRUE
            """,
            (info["id_sala"],),
        )
        alunos_sala = await cur.fetchall()
        medias_turma = []
        for al in alunos_sala:
            m = await _calcular_media_aluno_na_materia(conn, al["id_aluno"], id_sala_materia)
            if m is not None:
                medias_turma.append(m)
        media_turma = 7 # Valor fixo da média escolar

        total_aulas = len(aulas)
        pres_pct = round((len(presencas_set) / total_aulas) * 100, 2) if total_aulas > 0 else None

        return ProfessorAlunoResponse(
            professor=professor["nome"],
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
