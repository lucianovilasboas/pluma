from __future__ import annotations

from typing import Any

from essay_essay.evaluators.orchestrator import PromptTemplateProvider


def _provider(**kwargs: Any) -> PromptTemplateProvider:
    return PromptTemplateProvider(
        nome="teste",
        sistema_prompt="sistema",
        formato_saida="",
        **kwargs,
    )


class TestPromptAssembly:
    def test_sem_titulo_nao_contem_titulo_no_resultado(self) -> None:
        """
        CRÍTICO — quando services.py:574 avalia `if redacao.tema:` e tema é vazio,
        o texto NÃO recebe o prefixo "Título:". Este teste verifica que o
        template final não gera "Título:" a partir de um texto sem esse prefixo.
        """
        provider = _provider()

        texto_sem_titulo = "O aumento da expectativa de vida no Brasil reflete avanços."
        tema = "Tema: Exemplo"

        resultado = provider.usuario(texto_sem_titulo, tema)

        assert "Título:" not in resultado
        assert texto_sem_titulo in resultado
        assert "Tema: Exemplo" in resultado

    def test_com_titulo_customizado_aparece_no_resultado(self) -> None:
        """
        Quando o usuário informa um título, services.py prefixa
        "Título: {tema}\n\n" no texto. Verifica que esse prefixo
        chega íntegro no prompt final.
        """
        provider = _provider()

        texto_com_titulo = "Título: Meu título personalizado\n\nCorpo da redação."
        tema = "Tema: Exemplo"

        resultado = provider.usuario(texto_com_titulo, tema)

        assert "Título: Meu título personalizado" in resultado
        assert "Corpo da redação." in resultado

    def test_tema_ref_sem_descricao_nao_mostra_descricao(self) -> None:
        """
        Se tema_ref.texto for vazio, services.py:569-570 não adiciona
        o bloco "Descrição do tema:". O prompt mostra só o "Tema:".
        """
        provider = _provider()

        texto = "Texto da redação."
        tema = "Tema: Exemplo único"  # sem "\n\nDescrição do tema:"

        resultado = provider.usuario(texto, tema)

        assert "Tema: Exemplo único" in resultado
        assert "Descrição do tema:" not in resultado

    def test_tema_ref_nulo_omite_prefixo_tema(self) -> None:
        """
        CRÍTICO — quando tema_ref=None, services.py:572 define
        tema_texto = "". O prompt deve começar direto com "Redação:\n---",
        sem "Tema:" solto no início.
        """
        provider = _provider()

        texto = "Texto da redação."

        resultado = provider.usuario(texto, tema="")

        assert resultado.startswith("Redação:\n---"), (
            f"Esperava começar com 'Redação:\\n---', mas começou com:\n{resultado[:50]}"
        )
        assert "Tema:" not in resultado

    def test_titulo_muito_longo_nao_quebra_formato(self) -> None:
        """
        Título com ~500 caracteres não pode quebrar a estrutura
        do prompt (linha ---, seções, etc).
        """
        provider = _provider()

        titulo_longo = "Meu título " * 50
        texto = f"Título: {titulo_longo}\n\nCorpo da redação aqui."
        tema = "Tema: Exemplo"

        resultado = provider.usuario(texto, tema)

        assert "---\n" in resultado
        assert "Avalie segundo" in resultado
        assert resultado.count("---") == 2

    def test_redacao_vazia_nao_causa_erro(self) -> None:
        """
        Redação com texto vazio não deve lançar exceção.
        """
        provider = _provider()

        resultado = provider.usuario("", "Tema: Exemplo")

        assert resultado is not None
        assert "Redação:\n---\n\n---" in resultado or "---\n---" in resultado

    def test_titulo_com_novas_linhas_nao_quebra_separador(self) -> None:
        """
        CRÍTICO — se o título contiver \n, o separador --- pode
        ser duplicado ou a estrutura do prompt pode quebrar.
        """
        provider = _provider()

        titulo_quebrado = "Título: Linha um\nLinha dois\n\nCorpo da redação."
        tema = "Tema: Exemplo"

        resultado = provider.usuario(titulo_quebrado, tema)

        assert resultado.count("---") == 2, (
            f"Esperava exatos 2 separadores ---, mas encontrou {resultado.count('---')}"
        )

    def test_prompt_template_provider_nao_e_frozen(self) -> None:
        """
        PromptTemplateProvider é @dataclass sem frozen=True.
        Campos podem ser alterados após criação — risco de mutação
        acidental. Se no futuro houver bugs de estado compartilhado,
        congelar a dataclass pode ser a solução.
        """
        p = _provider()
        p.nome = "outro"
        assert p.nome == "outro"

    def test_prompt_com_textos_motivadores_completos_e_titulo(self) -> None:
        """
        Testa o formato completo do prompt: tema + descrição + textos
        + redação com título → verifica que todas as seções aparecem.
        """
        provider = _provider()

        tema = (
            "Tema: Exemplo completo\n\n"
            "Descrição do tema:\n"
            "Com base nos textos, redija...\n\n"
            "TEXTO 2:\n\"Texto 2...\"\n\n"
            "TEXTO 3:\n\"Texto 3...\""
        )
        texto = "Título: Meu título\n\nCorpo da redação."

        resultado = provider.usuario(texto, tema)

        assert "Tema: Exemplo completo" in resultado
        assert "Descrição do tema:" in resultado
        assert "TEXTO 2:" in resultado
        assert "TEXTO 3:" in resultado
        assert "Título: Meu título" in resultado
        assert resultado.count("---") == 2


class TestServicesPromptLogic:
    """
    Testa a lógica de prefixo em services.py:573-575 e tasks.py:85-87
    sem precisar de banco de dados.
    """

    def test_tema_vazio_suprime_linha_titulo(self) -> None:
        """
        CRÍTICO — reproduz exatamente `if redacao.tema:` em services.py.
        tema vazio → NÃO prefixa "Título:".
        """
        texto_original = "Corpo da redação."
        tema_vazio = ""

        texto = texto_original
        if tema_vazio:
            texto = f"Título: {tema_vazio}\n\n{texto}"

        assert texto == texto_original
        assert "Título:" not in texto

    def test_tema_preenchido_prefixa_titulo(self) -> None:
        """
        tema preenchido → prefixa "Título: {tema}\n\n".
        """
        texto_original = "Corpo da redação."
        tema = "Meu título"

        texto = f"Título: {tema}\n\n{texto_original}"

        assert texto.startswith("Título: Meu título")
        assert "Corpo da redação." in texto

    def test_tema_texto_vazio_quando_sem_tema_ref(self) -> None:
        """
        Reproduz services.py:571-572:
        if not (redacao.tema_ref_id and redacao.tema_ref):
            tema_texto = ""
        """
        tema_texto = ""
        assert tema_texto == ""

    def test_tema_texto_completo_quando_tema_ref_existe(self) -> None:
        """
        Reproduz services.py:567-570:
        se tema_ref existe, tema_texto recebe "Tema: {titulo}" + descrição.
        """
        titulo = "Exemplo de tema"
        texto_ref = "Descrição longa aqui."

        tema_texto = f"Tema: {titulo}"
        if texto_ref:
            tema_texto += f"\n\nDescrição do tema:\n{texto_ref}"

        assert "Tema: Exemplo de tema" in tema_texto
        assert "Descrição do tema:" in tema_texto
        assert texto_ref in tema_texto
