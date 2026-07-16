from __future__ import annotations

from essay_essay.evaluators.llm import (
    _limpar_justificativa,
    _nota_por_item,
    _sugestao_fallback,
    normalizar_resposta,
)


class TestLimparJustificativa:
    def test_remove_codigo_parenteses(self):
        resultado = _limpar_justificativa("Fuga total ao tema (NZ01).")
        assert resultado == "Fuga total ao tema."

    def test_remove_codigo_parenteses_sem_ponto(self):
        resultado = _limpar_justificativa("Fuga total ao tema (NZ01)")
        assert resultado == "Fuga total ao tema."

    def test_remove_codigo_colchetes(self):
        resultado = _limpar_justificativa("[NZ01] Fuga total ao tema")
        assert resultado == "Fuga total ao tema."

    def test_remove_codigo_no_meio(self):
        resultado = _limpar_justificativa(
            "Desvio grave (E01) de concordância verbal"
        )
        assert resultado == "Desvio grave de concordância verbal."

    def test_mantem_texto_sem_codigo(self):
        resultado = _limpar_justificativa(
            "Bom domínio da norma padrão, poucos desvios."
        )
        assert resultado == "Bom domínio da norma padrão, poucos desvios."

    def test_vazio_retorna_vazio(self):
        assert _limpar_justificativa("") == ""

    def test_adiciona_ponto_final(self):
        resultado = _limpar_justificativa("Texto sem ponto")
        assert resultado == "Texto sem ponto."


class TestSugestaoFallback:
    def test_fuga(self):
        sugestao = _sugestao_fallback("Fuga total ao tema detectada")
        assert "foco no tema" in sugestao
        assert "tangenciar" in sugestao

    def test_insuficiente(self):
        sugestao = _sugestao_fallback("Texto insuficiente para avaliação")
        assert "mínimo 7 linhas" in sugestao

    def test_branco(self):
        sugestao = _sugestao_fallback("Folha em branco")
        assert "número mínimo de linhas" in sugestao

    def test_letra(self):
        sugestao = _sugestao_fallback("Letra ilegível")
        assert "caligrafia" in sugestao and "legível" in sugestao

    def test_generico_quando_sem_keyword(self):
        sugestao = _sugestao_fallback("Nota zero por outro motivo")
        assert "Estude os critérios" in sugestao

    def test_case_insensitive(self):
        sugestao = _sugestao_fallback("FUGA TOTAL")
        assert "foco no tema" in sugestao


class TestNotaPorItem:
    def test_sugestao_vazia_nota_zero_preenche_fallback(self):
        item = {"nota": 0, "justificativa": "Fuga total ao tema", "sugestoes": ""}
        nota = _nota_por_item("c2", item)
        assert nota is not None
        assert nota.nota == 0
        assert "foco no tema" in nota.sugestoes

    def test_sugestao_vazia_nota_maior_zero_mantem_vazio(self):
        item = {"nota": 120, "justificativa": "Bom texto", "sugestoes": ""}
        nota = _nota_por_item("c2", item)
        assert nota is not None
        assert nota.nota == 120
        assert nota.sugestoes == ""

    def test_sugestao_preenchida_mantem_valor(self):
        item = {
            "nota": 160,
            "justificativa": "Bom texto",
            "sugestoes": "Continue praticando.",
        }
        nota = _nota_por_item("c1", item)
        assert nota is not None
        assert nota.sugestoes == "Continue praticando."

    def test_justificativa_limpa_codigos(self):
        item = {"nota": 0, "justificativa": "Fuga total (NZ01)", "sugestoes": ""}
        nota = _nota_por_item("c2", item)
        assert nota is not None
        assert "(NZ01)" not in nota.justificativa
        assert "Fuga total" in nota.justificativa

    def test_chave_invalida_retorna_none(self):
        item = {"nota": 80, "justificativa": "texto"}
        nota = _nota_por_item("invalida", item)
        assert nota is None


class TestNormalizarResposta:
    def test_remove_codigos_das_justificativas(self):
        dados = {
            "c1": {"nota": 0, "justificativa": "Fuga total (NZ01)", "sugestoes": ""},
            "c2": {"nota": 0, "justificativa": "Fuga total (NZ01)", "sugestoes": ""},
            "c3": {"nota": 0, "justificativa": "Fuga total (NZ01)", "sugestoes": ""},
            "c4": {"nota": 0, "justificativa": "Fuga total (NZ01)", "sugestoes": ""},
            "c5": {"nota": 0, "justificativa": "Fuga total (NZ01)", "sugestoes": ""},
        }
        result = normalizar_resposta(dados)
        assert "(NZ01)" not in result["c1"]["justificativa"]
        assert "(NZ01)" not in result["c2"]["justificativa"]

    def test_preenche_sugestoes_vazias_nota_zero(self):
        dados = {
            "c1": {"nota": 0, "justificativa": "Fuga total ao tema", "sugestoes": ""},
        }
        result = normalizar_resposta(dados)
        assert "foco no tema" in result["c1"]["sugestoes"]

    def test_mantem_sugestoes_existentes(self):
        dados = {
            "c1": {"nota": 80, "justificativa": "Bom texto", "sugestoes": "Continue."},
        }
        result = normalizar_resposta(dados)
        assert result["c1"]["sugestoes"] == "Continue."

    def test_nota_total_e_soma(self):
        dados = {
            "c1": {"nota": 160, "justificativa": "a", "sugestoes": ""},
            "c2": {"nota": 120, "justificativa": "b", "sugestoes": ""},
            "c3": {"nota": 80, "justificativa": "c", "sugestoes": ""},
            "c4": {"nota": 40, "justificativa": "d", "sugestoes": ""},
            "c5": {"nota": 0, "justificativa": "e", "sugestoes": ""},
        }
        result = normalizar_resposta(dados)
        assert result["nota_total"] == 400

    def test_dados_vazios_usam_padrao(self):
        result = normalizar_resposta({})
        assert result["c1"]["nota"] == 0
        assert result["c1"]["justificativa"] == ""
        assert result["nota_total"] == 0
        assert result["diagnostico"] == ""
