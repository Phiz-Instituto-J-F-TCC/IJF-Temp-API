# IJF-Temp-API-PhizLink

## Endpoint novo: buscar numero_phiz por CPF

### GET /aluno/numero-phiz-por-cpf

Retorna o número PhizLink do aluno a partir do CPF informado.

Parâmetro de query:

- cpf: CPF do aluno (aceita com ou sem pontuação)

Exemplos:

- /aluno/numero-phiz-por-cpf?cpf=12345678901
- /aluno/numero-phiz-por-cpf?cpf=123.456.789-01

Resposta de sucesso (200):

```json
{
  "aluno": "Nome do Aluno",
  "cpf": "123.456.789-01",
  "numero_phiz": "PHIZ12345"
}
```

Erros possíveis:

- 400: CPF inválido (quando não tiver 11 dígitos)
- 404: Aluno não encontrado para o CPF informado
