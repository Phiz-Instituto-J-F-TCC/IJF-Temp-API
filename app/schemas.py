from pydantic import BaseModel, EmailStr
from typing import Optional


# ========================
# Request Schemas
# ========================

class LinkarPhizRequest(BaseModel):
    email: str
    numero_phiz: str


# ========================
# Response Schemas
# ========================

class LinkarPhizResponse(BaseModel):
    mensagem: str
    tipo: str  # "aluno", "professor", "coordenador"
    nome: str


# --- Notas ---

class NotaDetalhe(BaseModel):
    avaliacao: str | None
    periodo: str
    valor: float
    peso: float


class MateriaNotas(BaseModel):
    materia: str
    sala: str
    notas: list[NotaDetalhe]
    media_ponderada: float


class RelatorioNotas(BaseModel):
    media_geral: float
    medias_por_materia: list[dict]


class AlunoNotasResponse(BaseModel):
    aluno: str
    materias: list[MateriaNotas]
    relatorio: RelatorioNotas


# --- Presença ---

class AulaPresenca(BaseModel):
    id_aula: int
    materia: str
    presente: bool


class RelatorioPresenca(BaseModel):
    total_aulas: int
    total_presencas: int
    total_faltas: int
    porcentagem_presenca: float


class AlunoPresencaResponse(BaseModel):
    aluno: str
    sala: str
    aulas: list[AulaPresenca]
    relatorio: RelatorioPresenca


# --- Aluno / Número Phiz por CPF ---

class AlunoPhizPorCpfResponse(BaseModel):
    aluno: str
    cpf: str
    numero_phiz: str


# --- Professor / Matéria ---

class AlunoResumoProfessor(BaseModel):
    nome: str
    numero_phiz: str | None
    media: float | None
    porcentagem_presenca: float | None


class RelatorioProfessorMateria(BaseModel):
    media_turma: float | None
    nota_mais_alta: float | None
    nota_mais_baixa: float | None
    alunos_acima_media: int
    alunos_abaixo_media: int
    porcentagem_presenca_turma: float | None


class ProfessorMateriaResponse(BaseModel):
    professor: str
    materia: str
    sala: str
    alunos: list[AlunoResumoProfessor]
    relatorio: RelatorioProfessorMateria


# --- Professor / Aluno ---

class RelatorioProfessorAluno(BaseModel):
    media_aluno: float | None
    media_turma: float | None
    porcentagem_presenca: float | None


class ProfessorAlunoResponse(BaseModel):
    professor: str
    aluno: str
    materia: str
    sala: str
    notas: list[NotaDetalhe]
    presencas: list[AulaPresenca]
    relatorio: RelatorioProfessorAluno


# --- Coordenador / Sala ---

class MateriaSalaResumo(BaseModel):
    materia: str
    id_sala_materia: int
    media_turma: float | None
    porcentagem_presenca: float | None


class CoordenadorSalaResponse(BaseModel):
    coordenador: str
    sala: str
    materias: list[MateriaSalaResumo]


# --- Coordenador / Aluno Geral ---

class CoordenadorAlunoGeralResponse(BaseModel):
    coordenador: str
    aluno: str
    sala: str
    materias: list[MateriaNotas]
    presenca_geral: RelatorioPresenca
    relatorio: RelatorioNotas


# --- Coordenador / Análises gerais ---

class CoordenadorAlunoAnaliseResumo(BaseModel):
    aluno: str
    numero_phiz: str | None
    sala: str
    media_geral: float | None
    porcentagem_presenca: float | None
    materias_avaliadas: int


class RelatorioCoordenadorAlunos(BaseModel):
    total_alunos: int
    alunos_com_notas: int
    alunos_com_presenca: int
    media_geral: float | None
    porcentagem_presenca_geral: float | None
    media_mais_alta: float | None
    media_mais_baixa: float | None


class CoordenadorAlunosGeralResponse(BaseModel):
    coordenador: str
    alunos: list[CoordenadorAlunoAnaliseResumo]
    relatorio: RelatorioCoordenadorAlunos


class CoordenadorSalaAnaliseResumo(BaseModel):
    sala: str
    total_alunos: int
    media_geral: float | None
    porcentagem_presenca: float | None


class RelatorioCoordenadorSerie(BaseModel):
    total_salas: int
    total_alunos: int
    alunos_com_notas: int
    alunos_com_presenca: int
    media_geral: float | None
    porcentagem_presenca_geral: float | None


class CoordenadorSerieGeralResponse(BaseModel):
    coordenador: str
    serie: int
    salas: list[CoordenadorSalaAnaliseResumo]
    relatorio: RelatorioCoordenadorSerie
