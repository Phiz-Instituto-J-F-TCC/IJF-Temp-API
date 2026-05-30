# Walkthrough — FastAPI PhizLink API

## Resumo

API FastAPI completa para consulta de dados acadêmicos do Instituto J.F. via número PhizLink, conectando ao PostgreSQL no NeonDB.

## Validações de Sala Atual (`aluno_sala.atual = true`)

Conforme solicitado, foi implementada a validação de que os dados retornados devem ser referentes apenas à sala ativa/atual do aluno em todas as buscas:

1. **`GET /aluno/notas`**:
   - A rota verifica se o aluno possui uma sala atual (`Aluno_Sala.atual = TRUE`). Se não possuir, retorna `404 Not Found` (com a mensagem `"Aluno não possui sala atual cadastrada."`).
   - A consulta de notas foi restrita à sala atual do aluno, garantindo que notas antigas de anos anteriores não sejam misturadas ao relatório.

2. **`GET /coordenador/aluno`**:
   - Adicionada validação de vínculo idêntica à do endpoint de professor. O endpoint agora valida se o aluno informado está ativo (`atual = TRUE`) na sala correspondente à matéria informada. Caso não esteja, retorna `403 Forbidden` (`"Aluno não pertence ou não está ativo nesta sala."`).

---

## Formato de Sala (`2A`, `3B`) e Busca de Matéria com Acentos Ignorados (`unaccent`)

Os endpoints de Professor e Coordenador utilizam parâmetros textuais amigáveis no lugar de IDs internos (`id_sala_materia`):

- **Sala**: Recebida no formato `2A`, `3B`, `1C`, etc. O sistema extrai dinamicamente o **ano** e a **letra** de forma case-insensitive, buscando no banco a sala correspondente. Caso o formato seja incorreto, retorna `400 Bad Request`. Caso a sala não exista, retorna `404 Not Found`.
- **Matéria (Sem Acento/Case-insensitive)**: A busca da matéria utiliza a extensão PostgreSQL nativa `unaccent` em conjunto com `ILIKE`:
  - `unaccent("nome") ILIKE unaccent(%s)`
  - Isso permite que buscas como `materia="matematica"` ou `materia="MATEMÁTICA"` encontrem o registro `"Matemática"` com sucesso, independentemente da presença de acentos ou diferença entre maiúsculas/minúsculas.
  - Para correspondências exatas em caso de múltiplos resultados, utilizamos a biblioteca standard do Python `unicodedata` para remover os acentos em nível de script e garantir a escolha da matéria correta.
  - Retorna `404 Not Found` informando erro descritivo se a matéria não for cadastrada ou não for lecionada na sala correspondente.

---

## Estrutura Final

```
IJF-Temp-API-PhizLink/
├── app/
│   ├── __init__.py
│   ├── main.py              # App FastAPI + CORS + lifespan
│   ├── database.py          # AsyncConnectionPool (psycopg3)
│   ├── schemas.py           # 15 Pydantic models
│   └── routers/
│       ├── __init__.py
│       ├── link.py           # POST /linkar-phiz
│       ├── aluno.py          # GET /aluno/notas, GET /aluno/presenca
│       ├── professor.py      # GET /professor/materia, GET /professor/aluno
│       └── coordenador.py    # 4 endpoints sem restrição de vínculo
├── .env.example
├── requirements.txt
└── script.sql
```

## Endpoints Disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/linkar-phiz` | Vincula PhizNumber a Coordenador/Professor/Aluno |
| GET | `/aluno/notas` | Notas da sala atual + relatório (média geral, por matéria) |
| GET | `/aluno/presenca` | Presença da sala atual + relatório (% participação) |
| GET | `/professor/materia` | Relatório da turma numa matéria (recebe `sala` e `materia`) |
| GET | `/professor/aluno` | Relatório individual na sala atual (recebe `sala`, `materia` e `numero_phiz_aluno`) |
| GET | `/coordenador/materia` | Igual professor/materia, sem restrição de vínculo do professor |
| GET | `/coordenador/aluno` | Igual professor/aluno, validando sala atual do aluno |
| GET | `/coordenador/sala` | Visão geral de todas as matérias de uma sala |
| GET | `/coordenador/aluno/geral` | Visão completa do aluno (todas as matérias + presença da sala atual) |
| GET | `/` | Health check |

---

## Como Rodar

1. Criar `.env` com a connection string do NeonDB:
   ```
   DATABASE_URL=postgresql://user:pass@ep-xxxx.us-east-2.aws.neon.tech/dbname?sslmode=require
   ```

2. Instalar dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. Rodar:
   ```bash
   uvicorn app.main:app --reload
   ```

4. Acessar Swagger UI: `http://localhost:8000/docs`
