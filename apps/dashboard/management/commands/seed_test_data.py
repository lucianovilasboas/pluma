from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.models import CustomUser, UserType
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM


class Command(BaseCommand):
    help = "Popula o banco com dados de teste"

    def add_arguments(self, parser):
        parser.add_argument("--openai-key", required=True)
        parser.add_argument("--deepseek-key", required=True)
        parser.add_argument("--deepseek-url", default="https://api.deepseek.com")

    def handle(self, *args, **options):
        openai_key = options["openai_key"]
        deepseek_key = options["deepseek_key"]
        deepseek_url = options["deepseek_url"]

        users = self._criar_usuarios()
        provedores = self._criar_provedores(openai_key, deepseek_key, deepseek_url)
        corretores_llm = self._criar_corretores_llm(provedores)
        self._criar_pool(users, corretores_llm)

    def _criar_usuarios(self):
        dados = [
            ("professor@example.com", "Professor", UserType.PROFESSOR),
            ("corretor@example.com", "Corretor", UserType.CORRETOR),
            ("aluno@example.com", "Aluno", UserType.ALUNO),
        ]
        criados = {}
        for email, nome, tipo in dados:
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults=dict(nome=nome, user_type=tipo, is_active=True),
            )
            if created:
                user.set_password("123")
                user.save(update_fields=["password"])
                self.stdout.write(self.style.SUCCESS(f"  {tipo}: {email} / 123"))
            else:
                self.stdout.write(f"  {tipo}: {email} (já existe)")
            criados[tipo] = user
        return criados

    def _criar_provedores(self, openai_key, deepseek_key, deepseek_url):
        dados = [
            ("OpenAI", openai_key, ""),
            ("DeepSeek", deepseek_key, deepseek_url),
        ]
        criados = {}
        for nome, api_key, base_url in dados:
            provedor, created = ProvedorLLM.objects.get_or_create(
                nome=nome,
                defaults=dict(api_key=api_key, base_url=base_url, ativo=True),
            )
            if not created:
                provedor.api_key = api_key
                provedor.base_url = base_url
                provedor.ativo = True
                provedor.save()
            self.stdout.write(self.style.SUCCESS(f"  Provedor: {nome}"))
            criados[nome] = provedor
        return criados

    def _criar_corretores_llm(self, provedores):
        dados = [
            ("GPT-4o", "gpt-4o", provedores["OpenAI"]),
            ("DeepSeek Chat", "deepseek-chat", provedores["DeepSeek"]),
        ]
        criados = {}
        for nome, modelo, provedor in dados:
            corretor, created = CorretorLLM.objects.get_or_create(
                nome=nome,
                defaults=dict(modelo=modelo, provedor=provedor),
            )
            if not created:
                corretor.modelo = modelo
                corretor.provedor = provedor
                corretor.save()
            self.stdout.write(self.style.SUCCESS(f"  Corretor LLM: {nome} ({modelo})"))
            criados[nome] = corretor
        return criados

    def _criar_pool(self, users, corretores_llm):
        pool, created = PoolCorrecao.objects.get_or_create(
            nome="Banca Padrão",
            defaults=dict(metodo="mediana", ativo=True),
        )
        if not created:
            pool.ativo = True
            pool.save(update_fields=["ativo"])

        PoolCorretor.objects.get_or_create(
            pool=pool,
            tipo="humano",
            usuario=users[UserType.CORRETOR],
            defaults=dict(peso=1.0, ordem=0),
        )
        PoolCorretor.objects.get_or_create(
            pool=pool,
            tipo="llm",
            corretor_llm=corretores_llm["GPT-4o"],
            defaults=dict(peso=1.0, ordem=1),
        )
        PoolCorretor.objects.get_or_create(
            pool=pool,
            tipo="llm",
            corretor_llm=corretores_llm["DeepSeek Chat"],
            defaults=dict(peso=1.0, ordem=2),
        )
        self.stdout.write(self.style.SUCCESS(f"  Banca: {pool.nome} (ativa)"))
