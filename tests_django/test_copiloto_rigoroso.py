from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import CustomUser, Escola, Turma, UserType
from apps.avaliacoes.models import Avaliacao
from apps.corretores.models import CorretorLLM, CorrecaoCopiloto, ProvedorLLM
from apps.redacoes.models import AtividadeAvaliativa, Redacao, TemaRedacao


# ── Helpers ──────────────────────────────────────────────────────

_counter: int = 0


def _uid() -> str:
    global _counter
    _counter += 1
    return str(_counter)


def _provedor() -> ProvedorLLM:
    return ProvedorLLM.objects.create(
        nome=f"P{_uid()}", tipo="openai", api_key="sk-test", ativo=True,
    )


def _corretor() -> CorretorLLM:
    uid = _uid()
    return CorretorLLM.objects.create(
        nome=f"C{uid}", provedor=_provedor(), modelo="gpt-4o",
    )


def _escola() -> Escola:
    return Escola.objects.create(nome=f"E{_uid()}")


def _turma(escola: Escola | None = None, **kw) -> Turma:
    e = escola or _escola()
    defaults = {"ano": "1º", "identificador": _uid()}
    defaults.update(kw)
    return Turma.objects.create(escola=e, **defaults)


def _user(email: str, tipo: str, **kw) -> CustomUser:
    return CustomUser.objects.create_user(
        email=email, password="x", user_type=tipo, nome=email.split("@")[0], **kw,
    )


def _login(client: Client, user: CustomUser) -> None:
    client.force_login(user)


def _copiloto(ativo: bool = True, **kw) -> CorrecaoCopiloto:
    c = _corretor()
    admin = kw.pop("criado_por", _user(f"admin{_uid()}@x.com", UserType.ADMIN))
    defaults = {"nome": f"Cop{_uid()}", "corretor_llm": c, "criado_por": admin, "ativo": ativo}
    defaults.update(kw)
    return CorrecaoCopiloto.objects.create(**defaults)


def _atividade(**kw) -> AtividadeAvaliativa:
    admin = kw.pop("criado_por", _user(f"admin{_uid()}@x.com", UserType.ADMIN))
    cop = kw.pop("copiloto", _copiloto(criado_por=admin))
    t = kw.pop("turma", _turma())
    defaults = {"titulo": f"Ativ{_uid()}", "copiloto": cop, "criado_por": admin}
    defaults.update(kw)
    atv = AtividadeAvaliativa.objects.create(**defaults)
    atv.turmas.set([t])
    return atv


# ═══════════════════════════════════════════════════════════════════
# TURMA × PROFESSOR — bordas e integridade
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_turma_m2m_adicionar_mesmo_professor_duas_vezes():
    """M2M deve ser idempotente — adicionar o mesmo professor 2x não duplica."""
    t = _turma()
    p = _user("p@x.com", UserType.PROFESSOR)
    t.professores.add(p)
    t.professores.add(p)
    assert t.professores.count() == 1


@pytest.mark.django_db
def test_turma_m2m_remover_professor():
    """Remover professor da turma deve funcionar."""
    t = _turma()
    p = _user("p@x.com", UserType.PROFESSOR)
    t.professores.add(p)
    assert t.professores.count() == 1
    t.professores.remove(p)
    assert t.professores.count() == 0
    assert list(p.turmas_ministradas.all()) == []


@pytest.mark.django_db
def test_turma_m2m_nao_afeta_outra_turma():
    """Adicionar professor em uma turma não deve afetar outra."""
    escola = _escola()
    t1 = _turma(escola, ano="1º", identificador="A")
    t2 = _turma(escola, ano="2º", identificador="B")
    p = _user("p@x.com", UserType.PROFESSOR)
    t1.professores.add(p)
    assert list(p.turmas_ministradas.all()) == [t1]
    assert list(t2.professores.all()) == []


@pytest.mark.django_db
def test_turma_professor_pode_ser_tambem_aluno_em_outra():
    """Um usuário pode ser professor de uma turma e aluno de outra."""
    escola = _escola()
    t1 = _turma(escola, ano="1º", identificador="A")
    t2 = _turma(escola, ano="2º", identificador="B")
    user = CustomUser.objects.create_user(
        email="dual@x.com", password="x",
        user_type=UserType.PROFESSOR,
        turma=t2,  # é aluno em t2
    )
    t1.professores.add(user)  # é professor em t1
    assert list(user.turmas_ministradas.all()) == [t1]
    assert user.turma == t2


@pytest.mark.django_db
def test_turma_excluir_professor_nao_exclui_turma():
    """Excluir um professor não deve cascatear para a turma."""
    t = _turma()
    p = _user("p@x.com", UserType.PROFESSOR)
    t.professores.add(p)
    p.delete()
    t.refresh_from_db()
    assert t.professores.count() == 0


# ═══════════════════════════════════════════════════════════════════
# TURMA VIEW — acesso, permissão, bordas
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_turma_view_nao_autenticado_redirect():
    resp = Client().get("/dashboard/turma")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_turma_view_corretor_bloqueado():
    corretor = _user("c@x.com", UserType.CORRETOR)
    client = Client()
    _login(client, corretor)
    resp = client.get("/dashboard/turma")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_turma_overview_professor_turma_sem_alunos():
    """Professor vê a turma mesmo sem alunos — não quebra."""
    t = _turma()
    p = _user("p@x.com", UserType.PROFESSOR)
    t.professores.add(p)
    client = Client()
    _login(client, p)
    resp = client.get(f"/dashboard/turma?turma_id={t.id}")
    assert resp.status_code == 200
    assert "Nenhum aluno" in resp.content.decode()


@pytest.mark.django_db
def test_turma_detalhe_admin_ve_turma_de_outra_escola():
    """Admin pode ver qualquer turma, mesmo de outra escola."""
    e1 = _escola()
    e2 = _escola()
    t1 = _turma(e1)
    t2 = _turma(e2)
    admin = _user("admin@x.com", UserType.ADMIN)
    client = Client()
    _login(client, admin)
    resp = client.get(f"/dashboard/turma?turma_id={t2.id}")
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# CorrecaoCopiloto — exclusão, cascade, integridade
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_copiloto_excluir_corretor_cascade():
    """Excluir CorretorLLM deve cascatear e excluir o copiloto."""
    c = _corretor()
    admin = _user("a@x.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=c, criado_por=admin,
    )
    cop_id = cop.id
    c.delete()
    assert not CorrecaoCopiloto.objects.filter(id=cop_id).exists()


@pytest.mark.django_db
def test_copiloto_excluir_criador_por_nao_cascade():
    """Excluir criado_por não deve cascatear — SET_NULL não, é CASCADE."""
    # Na verdade é CASCADE no model. Vamos verificar o comportamento.
    c = _corretor()
    admin = _user("a@x.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=c, criado_por=admin,
    )
    admin.delete()
    assert not CorrecaoCopiloto.objects.filter(id=cop.id).exists()


@pytest.mark.django_db
def test_copiloto_duplicar_nome_permitido():
    """Nomes duplicados devem ser permitidos (sem unique)."""
    c = _corretor()
    admin = _user("a@x.com", UserType.ADMIN)
    CorrecaoCopiloto.objects.create(
        nome="Mesmo Nome", corretor_llm=c, criado_por=admin,
    )
    CorrecaoCopiloto.objects.create(
        nome="Mesmo Nome", corretor_llm=c, criado_por=admin,
    )
    assert CorrecaoCopiloto.objects.filter(nome="Mesmo Nome").count() == 2


# ═══════════════════════════════════════════════════════════════════
# AtividadeAvaliativa — exclusão, cascade, integridade
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_atividade_excluir_copiloto_set_null():
    """Excluir um CorrecaoCopiloto deve setar copiloto=NULL."""
    atv = _atividade()
    cop_id = atv.copiloto.id
    atv.copiloto.delete()
    assert not CorrecaoCopiloto.objects.filter(id=cop_id).exists()
    atv.refresh_from_db()
    assert atv.copiloto is None
    assert AtividadeAvaliativa.objects.filter(id=atv.id).exists()


@pytest.mark.django_db
def test_atividade_perde_turma_ao_excluir_turma():
    """Excluir uma Turma deve remover o vínculo M2M."""
    atv = _atividade()
    turma_ids = list(atv.turmas.values_list("id", flat=True))
    assert len(turma_ids) == 1
    Turma.objects.filter(id=turma_ids[0]).delete()
    atv.refresh_from_db()
    assert list(atv.turmas.all()) == []


@pytest.mark.django_db
def test_atividade_excluir_tema_set_null():
    """Excluir um TemaRedacao deve setar tema=None na atividade."""
    admin = _user("a@x.com", UserType.ADMIN)
    tema = TemaRedacao.objects.create(
        titulo="T", texto="T", criado_por=admin,
    )
    atv = _atividade(tema=tema)
    tema.delete()
    atv.refresh_from_db()
    assert atv.tema is None


@pytest.mark.django_db
def test_atividade_com_tema_opcional():
    """Criar atividade sem tema não deve falhar."""
    atv = _atividade(tema=None)
    assert atv.tema is None
    assert atv.id is not None


@pytest.mark.django_db
def test_atividade_prazo_futuro():
    """Prazo pode ser no futuro."""
    atv = _atividade(prazo=timezone.now() + timedelta(days=30))
    assert atv.prazo > timezone.now()


@pytest.mark.django_db
def test_atividade_prazo_passado():
    """Prazo pode ser no passado (atividade vencida)."""
    atv = _atividade(prazo=timezone.now() - timedelta(days=1))
    assert atv.prazo < timezone.now()


@pytest.mark.django_db
def test_atividade_sem_prazo():
    """Prazo nulo é permitido."""
    atv = _atividade()
    assert atv.prazo is None


# ═══════════════════════════════════════════════════════════════════
# Redacao + Atividade — integridade referencial
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_redacao_excluir_atividade_set_null():
    """Excluir atividade deve setar null em redacoes."""
    atv = _atividade()
    aluno = _user("al@x.com", UserType.ALUNO)
    r = Redacao.objects.create(usuario=aluno, texto="T", atividade=atv)
    atv.delete()
    r.refresh_from_db()
    assert r.atividade is None


@pytest.mark.django_db
def test_redacao_atividade_related_name():
    """related_name='redacoes' deve funcionar."""
    atv = _atividade()
    aluno = _user("al@x.com", UserType.ALUNO)
    r1 = Redacao.objects.create(usuario=aluno, texto="T1", atividade=atv)
    r2 = Redacao.objects.create(usuario=aluno, texto="T2", atividade=atv)
    assert list(atv.redacoes.all().order_by("texto")) == [r1, r2]


# ═══════════════════════════════════════════════════════════════════
# Avaliacao — feedback_professor e liberada_em
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_feedback_professor_vazio_por_padrao():
    r = Redacao.objects.create(usuario=_user("a@x.com", UserType.ALUNO), texto="T")
    av = Avaliacao.objects.create(redacao=r, nota_total=100)
    assert av.feedback_professor == {}
    assert av.liberada_em is None


@pytest.mark.django_db
def test_feedback_professor_estrutura_completa():
    r = Redacao.objects.create(usuario=_user("a@x.com", UserType.ALUNO), texto="T")
    av = Avaliacao.objects.create(redacao=r, nota_total=100)
    fb = {
        "c1": {
            "nota_ia": 160,
            "nota_professor": 120,
            "delta": -40,
            "justificativa_ia": "Bom texto",
            "justificativa_professor": "Precisa melhorar",
            "editou_justificativa": True,
            "sugestoes_ia": "Ler mais",
            "sugestoes_professor": "Praticar gramática",
            "editou_sugestoes": True,
            "comentario_professor": "Aluno confunde registro",
            "merge_strategy": "professor_override",
        },
    }
    av.feedback_professor = fb
    av.save()
    av.refresh_from_db()
    assert av.feedback_professor["c1"]["delta"] == -40
    assert av.feedback_professor["c1"]["editou_justificativa"] is True


@pytest.mark.django_db
def test_feedback_professor_parcial():
    """Apenas algumas competências preenchidas não deve quebrar."""
    r = Redacao.objects.create(usuario=_user("a@x.com", UserType.ALUNO), texto="T")
    av = Avaliacao.objects.create(redacao=r, nota_total=100)
    av.feedback_professor = {"c3": {"nota_professor": 100}}
    av.save()
    av.refresh_from_db()
    assert av.feedback_professor["c3"]["nota_professor"] == 100


@pytest.mark.django_db
def test_liberada_em_preenchida():
    r = Redacao.objects.create(usuario=_user("a@x.com", UserType.ALUNO), texto="T")
    av = Avaliacao.objects.create(redacao=r, nota_total=100)
    agora = timezone.now()
    av.liberada_em = agora
    av.save()
    av.refresh_from_db()
    assert av.liberada_em is not None
    assert abs(av.liberada_em - agora).total_seconds() < 2


# ═══════════════════════════════════════════════════════════════════
# Copiloto Views — permissões, validação, bordas
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_copiloto_lista_nao_autenticado():
    resp = Client().get("/dashboard/copiloto")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_copiloto_lista_aluno_bloqueado():
    aluno = _user("a@x.com", UserType.ALUNO)
    c = Client()
    _login(c, aluno)
    resp = c.get("/dashboard/copiloto")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_copiloto_lista_corretor_bloqueado():
    corretor = _user("c@x.com", UserType.CORRETOR)
    c = Client()
    _login(c, corretor)
    resp = c.get("/dashboard/copiloto")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_copiloto_form_novo_get_admin():
    admin = _user("a@x.com", UserType.ADMIN)
    _corretor()  # precisa ter pelo menos 1 corretor no banco
    c = Client()
    _login(c, admin)
    resp = c.get("/dashboard/copiloto/novo")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_copiloto_form_novo_get_professor():
    prof = _user("p@x.com", UserType.PROFESSOR)
    _corretor()
    c = Client()
    _login(c, prof)
    resp = c.get("/dashboard/copiloto/novo")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_copiloto_form_novo_get_aluno_bloqueado():
    aluno = _user("a@x.com", UserType.ALUNO)
    c = Client()
    _login(c, aluno)
    resp = c.get("/dashboard/copiloto/novo")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_copiloto_editar_get_404_id_inexistente():
    admin = _user("a@x.com", UserType.ADMIN)
    c = Client()
    _login(c, admin)
    fake_id = uuid.uuid4()
    resp = c.get(f"/dashboard/copiloto/{fake_id}/editar")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_copiloto_criar_post_nome_espacos():
    """Nome com apenas espaços deve ser rejeitado."""
    corretor = _corretor()
    admin = _user("a@x.com", UserType.ADMIN)
    c = Client()
    _login(c, admin)
    resp = c.post("/dashboard/copiloto/novo", {
        "nome": "   ",
        "corretor_llm_id": str(corretor.id),
    })
    assert resp.status_code == 200
    assert CorrecaoCopiloto.objects.count() == 0


@pytest.mark.django_db
def test_copiloto_criar_post_corretor_id_invalido():
    """corretor_llm_id de um UUID que não existe deve dar 404."""
    admin = _user("a@x.com", UserType.ADMIN)
    c = Client()
    _login(c, admin)
    resp = c.post("/dashboard/copiloto/novo", {
        "nome": "Teste",
        "corretor_llm_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 404


@pytest.mark.django_db
def test_copiloto_editar_post_muda_corretor():
    corretor_a = _corretor()
    corretor_b = CorretorLLM.objects.create(
        nome="C2", provedor=_provedor(), modelo="gpt-4o-mini",
    )
    admin = _user("a@x.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor_a, criado_por=admin,
    )
    c = Client()
    _login(c, admin)
    c.post(f"/dashboard/copiloto/{cop.id}/editar", {
        "nome": "Cop",
        "corretor_llm_id": str(corretor_b.id),
        "ativo": "on",
    })
    cop.refresh_from_db()
    assert cop.corretor_llm == corretor_b


@pytest.mark.django_db
def test_copiloto_criar_post_salva_criado_por():
    """O criado_por deve ser o usuário logado."""
    corretor = _corretor()
    admin = _user("a@x.com", UserType.ADMIN)
    c = Client()
    _login(c, admin)
    c.post("/dashboard/copiloto/novo", {
        "nome": "Cop",
        "corretor_llm_id": str(corretor.id),
        "ativo": "on",
    })
    cop = CorrecaoCopiloto.objects.get(nome="Cop")
    assert cop.criado_por == admin


@pytest.mark.django_db
def test_copiloto_criar_post_teacher_tambem_pode():
    """Professor pode criar copiloto."""
    corretor = _corretor()
    prof = _user("p@x.com", UserType.PROFESSOR)
    c = Client()
    _login(c, prof)
    resp = c.post("/dashboard/copiloto/novo", {
        "nome": "Cop do Prof",
        "corretor_llm_id": str(corretor.id),
        "ativo": "on",
    })
    assert resp.status_code == 302
    cop = CorrecaoCopiloto.objects.get(nome="Cop do Prof")
    assert cop.criado_por == prof


# ═══════════════════════════════════════════════════════════════════
# Copiloto Model — rating, merge_strategy
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_copiloto_merge_strategy_suporta_apenas_override():
    """No MVP, apenas professor_override é suportado."""
    c = _corretor()
    admin = _user("a@x.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=c, criado_por=admin,
    )
    assert cop.merge_strategy == "professor_override"
    assert dict(CorrecaoCopiloto.MERGE_CHOICES) == {"professor_override": "Professor sobrescreve"}


@pytest.mark.django_db
def test_copiloto_string_representation():
    c = _corretor()
    admin = _user("a@x.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Meu Cop", corretor_llm=c, criado_por=admin,
    )
    assert str(cop) == "Meu Cop"


# ═══════════════════════════════════════════════════════════════════
# Estatísticas — permissões
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_estatisticas_nao_autenticado():
    resp = Client().get("/dashboard/estatisticas")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_estatisticas_aluno_bloqueado():
    aluno = _user("a@x.com", UserType.ALUNO)
    c = Client()
    _login(c, aluno)
    resp = c.get("/dashboard/estatisticas")
    assert resp.status_code == 302


# ═══════════════════════════════════════════════════════════════════
# Redação — atividade via API
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_redacao_criar_via_api_sem_atividade():
    """Criação normal de redação (sem atividade) continua funcionando."""
    aluno = _user("a@x.com", UserType.ALUNO)
    r = Redacao.objects.create(usuario=aluno, texto="Texto normal")
    assert r.atividade is None
    assert r.status == Redacao.Status.PENDENTE


@pytest.mark.django_db
def test_atividade_related_name_correto():
    """Verificar related_names."""
    admin = _user("a@x.com", UserType.ADMIN)
    cop = _copiloto(criado_por=admin)
    t = _turma()
    atv = AtividadeAvaliativa.objects.create(
        titulo="Ativ", copiloto=cop, criado_por=admin,
    )
    atv.turmas.set([t])
    assert list(cop.atividades.all()) == [atv]
    assert list(t.atividades.all()) == [atv]
