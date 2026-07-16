from __future__ import annotations

import os

from django.core.management.base import BaseCommand

from apps.corretores.models import (
    CorretorLLM,
    Ferramenta,
    PoolCorrecao,
    PoolCorretor,
    ProvedorLLM,
    Skill,
)

_ESPECIALISTAS = [
    {
        "nome": "Analista de Repertório",
        "descricao": (
            "Especialista na Competência 2 (Repertório Sociocultural) do ENEM. "
            "Analisa citações, dados históricos, obras culturais, autores e "
            "referências mobilizadas pelo candidato. Verifica pertinência, "
            "produtividade e integração do repertório à argumentação."
        ),
        "skills": ["Repertório Sociocultural"],
        "ferramentas": ["busca-repertorio"],
        "competencias": ["C2"],
    },
    {
        "nome": "Analista de Argumentação",
        "descricao": (
            "Especialista na Competência 3 (Estrutura Argumentativa) do ENEM. "
            "Analisa tese, desenvolvimento lógico, estratégias argumentativas "
            "(causa-consequência, exemplificação, contraposição) e conclusão. "
            "Identifica falácias, argumentação circular e generalizações vagas."
        ),
        "skills": ["Estrutura Argumentativa"],
        "ferramentas": [],
        "competencias": ["C3"],
    },
    {
        "nome": "Analista de Proposta",
        "descricao": (
            "Especialista na Competência 5 (Proposta de Intervenção) do ENEM. "
            "Examina os cinco elementos obrigatórios: agente, ação, modo/meio, "
            "efeito/finalidade e detalhamento. Verifica exequibilidade, respeito "
            "aos direitos humanos e coerência com o eixo temático."
        ),
        "skills": ["Proposta de Intervenção"],
        "ferramentas": ["calculadora-notas"],
        "competencias": ["C5"],
    },
    {
        "nome": "Analista de Linguagem",
        "descricao": (
            "Especialista na Competência 1 (Domínio da Norma Culta) do ENEM. "
            "Analisa ortografia, acentuação, pontuação, concordância "
            "verbal/nominal, regência e colocação pronominal. Distingue desvios "
            "graves de deslizes aceitáveis na modalidade escrita formal."
        ),
        "skills": ["Domínio da Norma Culta"],
        "ferramentas": ["ortografia", "verificador-gramatical"],
        "competencias": ["C1"],
    },
]

_ORQUESTRADOR = {
    "nome": "Avaliador ENEM Completo",
    "descricao": (
        "Orquestrador multiagente que coordena subagentes especializados e "
        "unifica as avaliações. Cobre a Competência 4 (Mecanismos Coesivos) "
        "como especialidade própria — conectivos, progressão referencial, "
        "articulação entre parágrafos e hierarquia de ideias."
    ),
    "skills": ["Mecanismos Coesivos"],
    "ferramentas": ["base_conhecimento"],
    "competencias": ["C4"],
    "subagentes": [
        "Analista de Repertório",
        "Analista de Argumentação",
        "Analista de Proposta",
        "Analista de Linguagem",
    ],
}

_POOL_NOME = "Banca Multiagente"


class Command(BaseCommand):
    help = (
        "Cria agentes de exemplo (especialistas + orquestrador) "
        "e uma banca para teste do fluxo multiagente."
    )

    def handle(self, **_kwargs):
        provedor = self._obter_provedor()
        if provedor is None:
            self.stdout.write(
                self.style.ERROR(
                    "Nenhum ProvedorLLM encontrado. Crie um provedor primeiro:\n"
                    "  Admin → Provedores IA → Adicionar (ex: OpenAI, com API key)\n"
                    "  ou configure OPENAI_API_KEY no .env"
                )
            )
            return

        modelo = os.getenv("LLM_MODEL", "gpt-4o")

        especialistas = self._criar_especialistas(provedor, modelo)
        orquestrador = self._criar_orquestrador(provedor, modelo, especialistas)
        self._criar_pool(orquestrador)

        self.stdout.write(self.style.SUCCESS("\nExemplos criados com sucesso!"))
        self.stdout.write(f"\n  Provedor:         {provedor.nome}")
        self.stdout.write(f"  Modelo:           {modelo}")
        self.stdout.write(f"  Especialistas:    {len(especialistas)}")
        self.stdout.write(f"  Orquestrador:     {orquestrador.nome}")
        self.stdout.write(f"  Banca ativa:      {_POOL_NOME}")
        self.stdout.write(
            "\n  Para testar:\n"
            "    1. Acesse Admin → Redações → criar redação\n"
            "    2. Na avaliação, selecione 'Banca Multiagente'\n"
            "    3. Ou via API: POST /api/avaliacoes/ com pool_id da banca\n"
        )

    def _obter_provedor(self) -> ProvedorLLM | None:
        provedor = ProvedorLLM.objects.filter(ativo=True).first()
        if provedor is not None:
            return provedor

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key == "sk-...":
            return None

        provedor, created = ProvedorLLM.objects.get_or_create(
            nome="OpenAI",
            defaults={"api_key": api_key, "ativo": True},
        )
        if created:
            self.stdout.write(
                self.style.WARNING(
                    "Provedor 'OpenAI' criado automaticamente com a chave do .env"
                )
            )
        return provedor

    def _criar_especialistas(
        self, provedor: ProvedorLLM, modelo: str
    ) -> list[CorretorLLM]:
        especialistas: list[CorretorLLM] = []
        for dados in _ESPECIALISTAS:
            agente, created = CorretorLLM.objects.get_or_create(
                nome=dados["nome"],
                defaults={
                    "provedor": provedor,
                    "modelo": modelo,
                    "descricao": dados["descricao"],
                    "competencias": dados["competencias"],
                },
            )
            if created:
                self._vincular_skills(agente, dados["skills"])
                self._vincular_ferramentas(agente, dados["ferramentas"])
                self.stdout.write(
                    self.style.SUCCESS(f"  + Criado: {agente.nome}")
                )
            else:
                self._vincular_skills(agente, dados["skills"])
                self._vincular_ferramentas(agente, dados["ferramentas"])
                self.stdout.write(f"  = Existente: {agente.nome} (atualizado)")

            especialistas.append(agente)
        return especialistas

    def _criar_orquestrador(
        self,
        provedor: ProvedorLLM,
        modelo: str,
        especialistas: list[CorretorLLM],
    ) -> CorretorLLM:
        orquestrador, created = CorretorLLM.objects.get_or_create(
            nome=_ORQUESTRADOR["nome"],
            defaults={
                "provedor": provedor,
                "modelo": modelo,
                "descricao": _ORQUESTRADOR["descricao"],
                "competencias": _ORQUESTRADOR["competencias"],
            },
        )

        self._vincular_skills(orquestrador, _ORQUESTRADOR["skills"])
        self._vincular_ferramentas(orquestrador, _ORQUESTRADOR["ferramentas"])

        orquestrador.subagentes.set(especialistas)

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"  + Criado: {orquestrador.nome} (orquestrador)")
            )
        else:
            self.stdout.write(f"  = Atualizado: {orquestrador.nome} (orquestrador)")

        return orquestrador

    def _criar_pool(self, orquestrador: CorretorLLM) -> PoolCorrecao:
        pool, created = PoolCorrecao.objects.get_or_create(
            nome=_POOL_NOME,
            defaults={
                "descricao": (
                    "Banca de teste do fluxo multiagente. Usa o orquestrador "
                    "'Avaliador ENEM Completo' que coordena 4 subagentes "
                    "especialistas em paralelo."
                ),
                "metodo": "mediana",
                "ativo": True,
            },
        )

        if not created:
            PoolCorretor.objects.filter(pool=pool).delete()
            self.stdout.write("  = Banca existente, recriando vínculos...")

        PoolCorretor.objects.create(
            pool=pool,
            tipo="llm",
            corretor_llm=orquestrador,
            peso=1.0,
            ordem=0,
        )

        PoolCorrecao.objects.filter(ativo=True).exclude(pk=pool.pk).update(ativo=False)

        self.stdout.write(
            self.style.SUCCESS(f"  + Banca '{_POOL_NOME}' ativada!")
        )
        return pool

    @staticmethod
    def _vincular_skills(agente: CorretorLLM, nomes: list[str]) -> None:
        skills = Skill.objects.filter(nome__in=nomes)
        agente.skills.set(skills)

    @staticmethod
    def _vincular_ferramentas(agente: CorretorLLM, slugs: list[str]) -> None:
        ferramentas = Ferramenta.objects.filter(slug__in=slugs)
        agente.ferramentas_ativas.set(ferramentas)
