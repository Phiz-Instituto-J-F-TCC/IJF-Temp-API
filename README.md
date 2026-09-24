# IJF-Temp-API-PhizLink

API para consulta de dados acadêmicos do Instituto J.F. via número PhizLink.

## Documentação de Endpoints

Base local sugerida: http://localhost:8000

### Geral

#### GET /

Retorna status da API e link da documentação interativa.

Resposta 200 (exemplo):

```json
{
  "mensagem": "PhizLink API está rodando.",
  "docs": "/docs"
}
```

#### GET /tipo-usuario/{numero_phiz}

Retorna o tipo de usuário vinculado ao número Phiz.

Parâmetros:

- numero_phiz (path)

Resposta 200 (exemplo):

```json
{
  "tipo": "aluno"
}
```

Erros possíveis:

- 404: número não pertence a nenhum usuário

### Link

#### POST /linkar-phiz

Vincula um número Phiz a um usuário pelo email institucional.

Body JSON:

```json
{
  "email": "usuario@exemplo.com",
  "numero_phiz": "PHIZ12345"
}
```

Resposta 200 (exemplo):

```json
{
  "mensagem": "Número PhizLink vinculado com sucesso ao aluno.",
  "tipo": "aluno",
  "nome": "Nome da Pessoa"
}
```

Erros possíveis:

- 404: email não encontrado

### Aluno

#### GET /aluno/notas

Retorna notas do aluno na sala atual, agrupadas por matéria.

Parâmetros de query:

- numero_phiz

#### GET /aluno/presenca

Retorna presenças e faltas do aluno na sala atual.

Parâmetros de query:

- numero_phiz

#### GET /aluno/numero-phiz-por-cpf

Retorna o número PhizLink do aluno a partir do CPF.

Parâmetros de query:

- cpf (aceita com ou sem pontuação)

Exemplos de chamada:

- /aluno/numero-phiz-por-cpf?cpf=12345678901
- /aluno/numero-phiz-por-cpf?cpf=123.456.789-01

Resposta 200 (exemplo):

```json
{
  "aluno": "Nome do Aluno",
  "cpf": "123.456.789-01",
  "numero_phiz": "PHIZ12345"
}
```

Erros possíveis:

- 400: CPF inválido (menos ou mais de 11 dígitos)
- 404: aluno não encontrado para o CPF informado

### Professor

#### GET /professor/materia

Relatório geral da turma em uma matéria, com validação de vínculo do professor.

Parâmetros de query:

- numero_phiz
- sala (formato AnoLetra, por exemplo: 2A)
- materia

#### GET /professor/aluno

Relatório detalhado de um aluno em uma matéria, com validação de vínculo do professor.

Parâmetros de query:

- numero_phiz
- sala
- materia
- nome_aluno

### Coordenador

#### GET /coordenador/materia

Relatório geral da turma em uma matéria, sem validação de vínculo de docência.

Parâmetros de query:

- numero_phiz
- sala
- materia

#### GET /coordenador/materia/geral

Resumo completo de uma matéria em todas as salas atuais, com médias por sala e relatório consolidado.

Parâmetros de query:

- numero_phiz
- materia

#### GET /coordenador/aluno

Relatório detalhado de um aluno em uma matéria.

Parâmetros de query:

- numero_phiz
- sala
- materia
- nome_aluno

#### GET /coordenador/sala

Visão geral da sala com todas as matérias.

Parâmetros de query:

- numero_phiz
- id_sala

#### GET /coordenador/aluno/geral

Visão geral completa de um aluno, incluindo todas as matérias, notas e presença.

Parâmetros de query:

- numero_phiz
- nome_aluno

#### GET /coordenador/alunos/geral

Analisa todos os alunos em suas salas atuais, com média e presença individuais e consolidadas.

Parâmetros de query:

- numero_phiz

#### GET /coordenador/serie/geral

Analisa uma série atual, agrupando os resultados por sala e apresentando o consolidado da série.

Parâmetros de query:

- numero_phiz
- ano (por exemplo: 1, 2 ou 3)

## Observações

- A documentação interativa pode ser acessada em /docs.
- Endpoints com numero_phiz exigem vínculo prévio do número via /linkar-phiz.
