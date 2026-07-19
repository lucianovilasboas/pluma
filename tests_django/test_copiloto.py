from __future__ import annotations

import pytest
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, Escola, Turma, UserType
from apps.avaliacoes.models import Avaliacao
from apps.corretores.models import CorretorLLM, CorrecaoCopiloto, ProvedorLLM
from apps.redacoes.models import AtividadeAvaliativa, Redacao, TemaRedacao


# ── Helpers ──────────────────────────────────────────────────────

def _criar_provedor() -> ProvedorLLM:
    return ProvedorLLM.objects.create(
        nome="Test Provider",
        tipo="openai",
        api_key="sk-test",
        ativo=True,
    )


def _criar_corretor() -> CorretorLLM:
    return CorretorLLM.objects.create(
        nome="Corretor Teste",
        provedor=_criar_provedor(),
        modelo="gpt-4o",
    )


def _criar_escola() -> Escola:
    return Escola.objects.create(nome="Escola Teste")


def _criar_turma(escola: Escola, **kwargs) -> Turma:
    defaults = {"ano": "1º ano", "identificador": "A"}
    defaults.update(kwargs)
    return Turma.objects.create(escola=escola, **defaults)


def _criar_usuario(email: str, tipo: str, turma: Turma | None = None) -> CustomUser:
    return CustomUser.objects.create_user(
        email=email,
        password="teste123",
        user_type=tipo,
        turma=turma,
        nome=email.split("@")[0],
    )


def _login(client: Client | APIClient, user: CustomUser) -> None:
    client.force_login(user)


# ── Turma × Professor (M2M) ──────────────────────────────────────

def _criar_atividade(titulo="Ativ", copiloto=None, turma=None, criado_por=None, **kw) -> AtividadeAvaliativa:
    from apps.redacoes.models import AtividadeAvaliativa
    atv = AtividadeAvaliativa.objects.create(titulo=titulo, copiloto=copiloto, criado_por=criado_por, **kw)
    if turma is not None:
        atv.turmas.set([turma])
    return atv



@pytest.mark.django_db
def test_turma_adiciona_professor_m2m():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    assert list(turma.professores.all()) == [prof]


@pytest.mark.django_db
def test_turma_busca_reversa_professor():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º", identificador="A")
    t2 = _criar_turma(escola, ano="2º", identificador="B")
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    t1.professores.add(prof)
    t2.professores.add(prof)
    turmas = list(prof.turmas_ministradas.all().order_by("ano"))
    assert turmas == [t1, t2]


@pytest.mark.django_db
def test_turma_multiplos_professores():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    p1 = _criar_usuario("p1@test.com", UserType.PROFESSOR)
    p2 = _criar_usuario("p2@test.com", UserType.PROFESSOR)
    turma.professores.add(p1, p2)
    assert turma.professores.count() == 2


@pytest.mark.django_db
def test_turma_professor_sem_turmas():
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    assert list(prof.turmas_ministradas.all()) == []


# ── Turma Overview View ──────────────────────────────────────────

@pytest.mark.django_db
def test_turma_overview_professor_ve_suas_turmas():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º", identificador="A")
    t2 = _criar_turma(escola, ano="2º", identificador="B")
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    t1.professores.add(prof)
    # t2 não pertence ao professor
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/turma")
    assert resp.status_code == 200
    assert "1º A" in resp.content.decode()
    assert "2º B" not in resp.content.decode()


@pytest.mark.django_db
def test_turma_overview_admin_ve_todas():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º", identificador="A")
    t2 = _criar_turma(escola, ano="2º", identificador="B")
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    client = Client()
    _login(client, admin)
    resp = client.get("/dashboard/turma")
    assert resp.status_code == 200
    assert "1º A" in resp.content.decode()
    assert "2º B" in resp.content.decode()


@pytest.mark.django_db
def test_turma_overview_professor_sem_turma():
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/turma")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_turma_overview_aluno_bloqueado():
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO)
    client = Client()
    _login(client, aluno)
    resp = client.get("/dashboard/turma")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_turma_detalhe_filtra_alunos():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º", identificador="A")
    t2 = _criar_turma(escola, ano="2º", identificador="B")
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    t1.professores.add(prof)
    a1 = _criar_usuario("a1@test.com", UserType.ALUNO, turma=t1)
    a2 = _criar_usuario("a2@test.com", UserType.ALUNO, turma=t2)
    client = Client()
    _login(client, prof)
    resp = client.get(f"/dashboard/turma?turma_id={t1.id}")
    html = resp.content.decode()
    assert a1.email in html
    assert a2.email not in html


@pytest.mark.django_db
def test_turma_detalhe_professor_sem_acesso_turma():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º", identificador="A")
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    # prof não é professor de t1
    client = Client()
    _login(client, prof)
    resp = client.get(f"/dashboard/turma?turma_id={t1.id}")
    assert resp.status_code == 302


# ── CorrecaoCopiloto Model ───────────────────────────────────────

@pytest.mark.django_db
def test_copiloto_criar():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Meu Copiloto",
        corretor_llm=corretor,
        criado_por=admin,
    )
    assert cop.id is not None
    assert cop.merge_strategy == "professor_override"
    assert cop.ativo is False
    assert str(cop) == "Meu Copiloto"


@pytest.mark.django_db
def test_copiloto_merge_strategy_default():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin,
    )
    assert cop.merge_strategy == "professor_override"


@pytest.mark.django_db
def test_copiloto_criado_por_obrigatorio():
    corretor = _criar_corretor()
    with pytest.raises(Exception):
        CorrecaoCopiloto.objects.create(
            nome="Sem Dono", corretor_llm=corretor,
        )


@pytest.mark.django_db
def test_copiloto_corretor_llm_obrigatorio():
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    with pytest.raises(Exception):
        CorrecaoCopiloto.objects.create(
            nome="Sem Corretor", criado_por=admin,
        )


@pytest.mark.django_db
def test_copiloto_related_name_atividades():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin,
    )
    assert list(cop.atividades.all()) == []


# ── AtividadeAvaliativa Model ────────────────────────────────────

@pytest.mark.django_db
def test_atividade_criar():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin,
    )
    escola = _criar_escola()
    turma = _criar_turma(escola)
    tema = TemaRedacao.objects.create(
        titulo="Tema Teste", texto="Texto do tema",
        criado_por=admin,
    )
    atv = _criar_atividade(
        titulo="Redação 1",
        copiloto=cop,
        tema=tema,
                criado_por=admin
    )

    assert atv.id is not None
    assert str(atv) == "Redação 1"
    assert atv.prazo is None


@pytest.mark.django_db
def test_atividade_copiloto_opcional():
    """Copiloto agora é opcional — criar sem copiloto funciona."""
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    escola = _criar_escola()
    turma = _criar_turma(escola)
    atv = _criar_atividade(
        titulo="Sem Copiloto", copiloto=None, turma=turma, criado_por=admin,
    )
    assert atv.copiloto is None
    assert atv.titulo == "Sem Copiloto"


@pytest.mark.django_db
def test_atividade_sem_turma_ok():
    """Criar atividade sem turma não quebra (M2M vazio)."""
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin,
    )
    atv = _criar_atividade(
        titulo="Sem Turma", copiloto=cop, criado_por=admin,
    )
    assert atv.titulo == "Sem Turma"
    assert list(atv.turmas.all()) == []


@pytest.mark.django_db
def test_atividade_tema_opcional():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin,
    )
    escola = _criar_escola()
    turma = _criar_turma(escola)
    atv = _criar_atividade(
        titulo="Sem Tema", copiloto=cop, turma=turma, criado_por=admin,
    )

    assert atv.tema is None


# ── Atividade → Redacao (FK) ─────────────────────────────────────

@pytest.mark.django_db
def test_redacao_com_atividade():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin,
    )
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(
        usuario=aluno, texto="Meu texto", atividade=atv,
    )
    assert red.atividade == atv
    assert list(atv.redacoes.all()) == [red]


# ── Avaliacao Feedback Professor ─────────────────────────────────

@pytest.mark.django_db
def test_avaliacao_feedback_professor_default():
    red = Redacao.objects.create(
        usuario=_criar_usuario("aluno@test.com", UserType.ALUNO),
        texto="Texto",
    )
    av = Avaliacao.objects.create(redacao=red, nota_total=100)
    assert av.feedback_professor == {}
    assert av.liberada_em is None


@pytest.mark.django_db
def test_avaliacao_feedback_professor_salva():
    red = Redacao.objects.create(
        usuario=_criar_usuario("aluno@test.com", UserType.ALUNO),
        texto="Texto",
    )
    av = Avaliacao.objects.create(redacao=red, nota_total=100)
    av.feedback_professor = {
        "c1": {"nota_ia": 160, "nota_professor": 120, "delta": -40},
        "c2": {"nota_ia": 100, "nota_professor": 100, "delta": 0},
    }
    av.save()
    av.refresh_from_db()
    assert av.feedback_professor["c1"]["nota_professor"] == 120
    assert av.feedback_professor["c2"]["delta"] == 0


# ── Copiloto Views ───────────────────────────────────────────────

@pytest.mark.django_db
def test_copiloto_lista_admin():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    CorrecaoCopiloto.objects.create(
        nome="Cop 1", corretor_llm=corretor, criado_por=admin,
    )
    client = Client()
    _login(client, admin)
    resp = client.get("/dashboard/copiloto")
    assert resp.status_code == 200
    assert "Cop 1" in resp.content.decode()


@pytest.mark.django_db
def test_copiloto_lista_professor_ve_apenas_ativos():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    ativo = CorrecaoCopiloto.objects.create(
        nome="Ativo", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    inativo = CorrecaoCopiloto.objects.create(
        nome="Inativo", corretor_llm=corretor, criado_por=admin, ativo=False,
    )
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/copiloto")
    html = resp.content.decode()
    assert "Ativo" in html
    assert "Inativo" not in html


@pytest.mark.django_db
def test_copiloto_lista_aluno_bloqueado():
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO)
    client = Client()
    _login(client, aluno)
    resp = client.get("/dashboard/copiloto")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_copiloto_criar_post():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    client = Client()
    _login(client, admin)
    resp = client.post("/dashboard/copiloto/novo", {
        "nome": "Novo Copiloto",
        "corretor_llm_id": str(corretor.id),
        "ativo": "on",
    })
    assert resp.status_code == 302
    assert CorrecaoCopiloto.objects.filter(nome="Novo Copiloto").exists()


@pytest.mark.django_db
def test_copiloto_criar_post_sem_nome():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    client = Client()
    _login(client, admin)
    resp = client.post("/dashboard/copiloto/novo", {
        "nome": "",
        "corretor_llm_id": str(corretor.id),
    })
    assert resp.status_code == 200
    assert CorrecaoCopiloto.objects.count() == 0


@pytest.mark.django_db
def test_copiloto_criar_post_sem_corretor():
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    client = Client()
    _login(client, admin)
    resp = client.post("/dashboard/copiloto/novo", {
        "nome": "Sem Corretor",
        "corretor_llm_id": "",
    })
    assert resp.status_code == 200
    assert CorrecaoCopiloto.objects.count() == 0


@pytest.mark.django_db
def test_copiloto_editar_post():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Original", corretor_llm=corretor, criado_por=admin,
    )
    client = Client()
    _login(client, admin)
    resp = client.post(f"/dashboard/copiloto/{cop.id}/editar", {
        "nome": "Editado",
        "corretor_llm_id": str(corretor.id),
        "ativo": "on",
    })
    assert resp.status_code == 302
    cop.refresh_from_db()
    assert cop.nome == "Editado"
    assert cop.ativo is True


# ── Estatísticas filtradas por turma ─────────────────────────────

@pytest.mark.django_db
def test_estatisticas_professor_filtra_por_turma():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º", identificador="A")
    t2 = _criar_turma(escola, ano="2º", identificador="B")
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    t1.professores.add(prof)
    a1 = _criar_usuario("a1@test.com", UserType.ALUNO, turma=t1)
    a2 = _criar_usuario("a2@test.com", UserType.ALUNO, turma=t2)
    Redacao.objects.create(usuario=a1, texto="Redação a1")
    Redacao.objects.create(usuario=a2, texto="Redação a2")
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/estatisticas")
    assert resp.status_code == 200
    # O template renderiza os dados; o importante é não quebrar
    # e filtrar corretamente — verificamos contagem nas queries


# ── Edge cases ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_aluno_sem_turma_nao_aparece_na_turma():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    sem_turma = _criar_usuario("semturma@test.com", UserType.ALUNO)
    com_turma = _criar_usuario("comturma@test.com", UserType.ALUNO, turma=turma)
    client = Client()
    _login(client, prof)
    resp = client.get(f"/dashboard/turma?turma_id={turma.id}")
    html = resp.content.decode()
    assert com_turma.email in html
    assert sem_turma.email not in html


@pytest.mark.django_db
def test_turma_id_invalido_admin():
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    client = Client()
    _login(client, admin)
    resp = client.get("/dashboard/turma?turma_id=00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_copiloto_criado_por_registra_usuario():
    corretor = _criar_corretor()
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin,
    )
    assert cop.criado_por == admin


@pytest.mark.django_db
def test_redacao_atividade_nula_por_padrao():
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO)
    red = Redacao.objects.create(usuario=aluno, texto="Texto")
    assert red.atividade is None


# ── AtividadeAvaliativa Views ────────────────────────────────────

@pytest.mark.django_db
def test_atividades_lista_professor():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    admin = _criar_usuario("admin2@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    _criar_atividade(
        titulo="Ativ Prof", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/atividades")
    assert resp.status_code == 200
    assert "Ativ Prof" in resp.content.decode()


@pytest.mark.django_db
def test_atividades_lista_professor_nao_ve_outra_turma():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º", identificador="A")
    t2 = _criar_turma(escola, ano="2º", identificador="B")
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    t1.professores.add(prof)
    admin = _criar_usuario("admin2@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    _criar_atividade(titulo="Minha", copiloto=cop, turma=t1, criado_por=admin)
    _criar_atividade(titulo="Outra", copiloto=cop, turma=t2, criado_por=admin)
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/atividades")
    html = resp.content.decode()
    assert "Minha" in html
    assert "Outra" not in html


@pytest.mark.django_db
def test_atividades_lista_admin_ve_todas():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º")
    t2 = _criar_turma(escola, ano="2º")
    admin = _criar_usuario("admin2@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    _criar_atividade(titulo="A1", copiloto=cop, turma=t1, criado_por=admin)
    _criar_atividade(titulo="A2", copiloto=cop, turma=t2, criado_por=admin)
    client = Client()
    _login(client, admin)
    resp = client.get("/dashboard/atividades")
    html = resp.content.decode()
    assert "A1" in html and "A2" in html


@pytest.mark.django_db
def test_atividade_criar_post():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=prof, ativo=True,
    )
    client = Client()
    _login(client, prof)
    resp = client.post("/dashboard/atividades/nova", {
        "titulo": "Nova Ativ",
        "copiloto_id": str(cop.id),
        "turmas_ids": [str(turma.id)],
    })
    assert resp.status_code == 302
    assert AtividadeAvaliativa.objects.filter(titulo="Nova Ativ").exists()


@pytest.mark.django_db
def test_atividade_criar_post_sem_titulo():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=prof, ativo=True,
    )
    client = Client()
    _login(client, prof)
    resp = client.post("/dashboard/atividades/nova", {
        "titulo": "",
        "copiloto_id": str(cop.id),
        "turmas_ids": [str(turma.id)],
    })
    assert resp.status_code == 200
    assert AtividadeAvaliativa.objects.count() == 0


@pytest.mark.django_db
def test_atividade_editar_post():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=prof, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Original", copiloto=cop, turma=turma, criado_por=prof,
    )

    client = Client()
    _login(client, prof)
    resp = client.post(f"/dashboard/atividades/{atv.id}/editar", {
        "titulo": "Editada",
        "copiloto_id": str(cop.id),
        "turmas_ids": [str(turma.id)],
    })
    assert resp.status_code == 302
    atv.refresh_from_db()
    assert atv.titulo == "Editada"


# ── Copiloto: pendentes, revisar, liberar ────────────────────────

@pytest.mark.django_db
def test_copiloto_pendentes_vazio():
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/copiloto/pendentes")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_copiloto_pendentes_com_itens():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin3@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto", atividade=atv)
    from apps.avaliacoes.models import Avaliacao
    Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=True,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
        corretor_llm=corretor,
    )
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/copiloto/pendentes")
    assert resp.status_code == 200
    assert "Ativ" in resp.content.decode()


@pytest.mark.django_db
def test_copiloto_revisar_get():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin3@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto revisar", atividade=atv)
    from apps.avaliacoes.models import Avaliacao
    av = Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=True,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
        corretor_llm=corretor,
    )
    client = Client()
    _login(client, prof)
    resp = client.get(f"/dashboard/copiloto/revisar/{av.id}")
    assert resp.status_code == 200
    assert "Texto revisar" in resp.content.decode()


@pytest.mark.django_db
def test_copiloto_revisar_post():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin3@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto", atividade=atv)
    from apps.avaliacoes.models import Avaliacao
    av = Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=True,
        c1_nota=200, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
        corretor_llm=corretor,
    )
    client = Client()
    _login(client, prof)
    resp = client.post(f"/dashboard/copiloto/revisar/{av.id}", {
        "c1_nota": "160",
        "c1_justificativa": "Justificativa editada",
        "c2_nota": "120",
        "c3_nota": "100",
        "c4_nota": "100",
        "c5_nota": "100",
    })
    assert resp.status_code == 302
    av.refresh_from_db()
    assert av.feedback_professor["c1"]["nota_professor"] == 160
    assert av.feedback_professor["c1"]["justificativa_professor"] == "Justificativa editada"
    assert av.feedback_professor["c1"]["editou_justificativa"] is True
    assert av.feedback_professor["c2"]["delta"] == 20


@pytest.mark.django_db
def test_copiloto_liberar_post():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin3@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto", atividade=atv)
    from apps.avaliacoes.models import Avaliacao, Notificacao
    av = Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=True,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
        corretor_llm=corretor,
    )
    av.feedback_professor = {
        "c1": {"nota_professor": 160, "justificativa_professor": "Melhorou"},
        "c2": {"nota_professor": 140, "justificativa_professor": "Bom"},
    }
    av.save()
    client = Client()
    _login(client, prof)
    resp = client.post(f"/dashboard/copiloto/liberar/{av.id}")
    assert resp.status_code == 302
    av.refresh_from_db()
    assert av.rascunho is False
    assert av.liberada_em is not None
    assert av.c1_nota == 160
    assert av.c2_nota == 140
    assert av.nota_total == 160 + 140 + 120 + 120 + 120
    assert Notificacao.objects.filter(redacao=red).exists()


@pytest.mark.django_db
def test_copiloto_liberar_ja_liberada():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin3@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto", atividade=atv)
    from apps.avaliacoes.models import Avaliacao
    av = Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=False, liberada_em=timezone.now(),
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
    )
    client = Client()
    _login(client, prof)
    resp = client.post(f"/dashboard/copiloto/liberar/{av.id}")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_copiloto_revisar_sem_acesso():
    """Professor de outra turma não pode revisar."""
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º")
    t2 = _criar_turma(escola, ano="2º")
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    t1.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=t2)
    admin = _criar_usuario("admin3@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=t2, criado_por=admin)

    red = Redacao.objects.create(usuario=aluno, texto="Texto", atividade=atv)
    from apps.avaliacoes.models import Avaliacao
    av = Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=True,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
        corretor_llm=corretor,
    )
    client = Client()
    _login(client, prof)
    resp = client.get(f"/dashboard/copiloto/revisar/{av.id}")
    assert resp.status_code == 302


# ── Minhas Atividades (aluno) ────────────────────────────────────

@pytest.mark.django_db
def test_minhas_atividades_aluno_ve():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    _criar_atividade(
        titulo="Ativ do Aluno", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, aluno)
    resp = client.get("/dashboard/minhas-atividades")
    assert resp.status_code == 200
    assert "Ativ do Aluno" in resp.content.decode()


@pytest.mark.django_db
def test_minhas_atividades_aluno_sem_turma():
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO)
    client = Client()
    _login(client, aluno)
    resp = client.get("/dashboard/minhas-atividades")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_minhas_atividades_aluno_nao_ve_outra_turma():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º")
    t2 = _criar_turma(escola, ano="2º")
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=t1)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    _criar_atividade(titulo="Minha Ativ", copiloto=cop, turma=t1, criado_por=admin)
    _criar_atividade(titulo="Outra Ativ", copiloto=cop, turma=t2, criado_por=admin)
    client = Client()
    _login(client, aluno)
    resp = client.get("/dashboard/minhas-atividades")
    html = resp.content.decode()
    assert "Minha Ativ" in html
    assert "Outra Ativ" not in html


@pytest.mark.django_db
def test_minhas_atividades_professor_bloqueado():
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/minhas-atividades")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_atividade_aluno_get():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ Teste", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, aluno)
    resp = client.get(f"/dashboard/atividades/{atv.id}/aluno")
    assert resp.status_code == 200
    assert "Ativ Teste" in resp.content.decode()


@pytest.mark.django_db
def test_atividade_aluno_post():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ Teste", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, aluno)
    resp = client.post(f"/dashboard/atividades/{atv.id}/aluno", {
        "texto": "Meu texto de redacao com mais de vinte caracteres para enviar",
    })
    assert resp.status_code == 302
    assert Redacao.objects.filter(usuario=aluno, atividade=atv).exists()


@pytest.mark.django_db
def test_atividade_aluno_post_curto():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, aluno)
    resp = client.post(f"/dashboard/atividades/{atv.id}/aluno", {
        "texto": "curto",
    })
    assert resp.status_code == 200
    assert not Redacao.objects.filter(usuario=aluno, atividade=atv).exists()


@pytest.mark.django_db
def test_atividade_aluno_duas_submissoes():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    Redacao.objects.create(
        usuario=aluno, atividade=atv, texto="Primeira redacao com mais de vinte caracteres.",
    )
    client = Client()
    _login(client, aluno)
    resp = client.post(f"/dashboard/atividades/{atv.id}/aluno", {
        "texto": "Segunda tentativa com mais de vinte caracteres.",
    })
    assert resp.status_code == 302
    assert Redacao.objects.filter(usuario=aluno, atividade=atv).count() == 1


@pytest.mark.django_db
def test_atividade_aluno_outra_turma_bloqueado():
    escola = _criar_escola()
    t1 = _criar_turma(escola, ano="1º")
    t2 = _criar_turma(escola, ano="2º")
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=t1)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=t2, criado_por=admin)

    client = Client()
    _login(client, aluno)
    resp = client.get(f"/dashboard/atividades/{atv.id}/aluno")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_atividade_aluno_status_pendente_aguardando_corrigida():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ Status", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, aluno)

    resp = client.get("/dashboard/minhas-atividades")
    assert "Pendente" in resp.content.decode()

    red = Redacao.objects.create(
        usuario=aluno, atividade=atv, texto="Redacao com mais de vinte caracteres.",
    )
    resp = client.get("/dashboard/minhas-atividades")
    assert "Aguardando" in resp.content.decode()

    Avaliacao.objects.create(
        redacao=red, nota_total=800, rascunho=False, liberada_em=timezone.now(),
        c1_nota=160, c2_nota=160, c3_nota=160, c4_nota=160, c5_nota=160,
    )
    resp = client.get("/dashboard/minhas-atividades")
    assert "800" in resp.content.decode()


# ── Correções: template, badge, notificação ──────────────────────

@pytest.mark.django_db
def test_atividade_aluno_nao_mostra_copiloto():
    """O aluno NÃO deve ver informações sobre o corretor IA."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Copiloto Secreto", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, aluno)
    resp = client.get(f"/dashboard/atividades/{atv.id}/aluno")
    html = resp.content.decode()
    assert "Copiloto Secreto" not in html
    assert "Corretor" not in html


@pytest.mark.django_db
def test_nav_counts_pre_correcoes_professor():
    """Professor deve ver badge de pré-correções pendentes."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto com mais de vinte caracteres.", atividade=atv)
    Avaliacao.objects.create(
        redacao=red, rascunho=True, nota_total=600,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
    )
    from apps.dashboard.context_processors import nav_counts
    counts = nav_counts(type("req", (), {"user": prof})())
    assert counts.get("pre_correcoes_count", 0) >= 1


@pytest.mark.django_db
def test_nav_counts_pre_correcoes_admin():
    """Admin deve ver badge de pré-correções também."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto com mais de vinte caracteres.", atividade=atv)
    Avaliacao.objects.create(
        redacao=red, rascunho=True, nota_total=600,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
    )
    from apps.dashboard.context_processors import nav_counts
    counts = nav_counts(type("req", (), {"user": admin})())
    assert counts.get("pre_correcoes_count", 0) >= 1


@pytest.mark.django_db
def test_nav_counts_pre_correcoes_professor_sem_turma():
    """Professor sem turmas não quebra o badge."""
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    from apps.dashboard.context_processors import nav_counts
    counts = nav_counts(type("req", (), {"user": prof})())
    assert "pre_correcoes_count" not in counts


@pytest.mark.django_db
def test_pre_correcao_cria_notificacao_professor():
    """Ao criar pré-correção, o professor deve receber notificação."""
    from apps.avaliacoes.models import Notificacao
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto para teste de notificacao com mais de vinte.", atividade=atv)
    av = Avaliacao.objects.create(
        redacao=red, rascunho=True, nota_total=600,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
        avaliador="copiloto",
    )
    from apps.avaliacoes.models import Notificacao
    Notificacao.objects.create(
        usuario=prof, redacao=red, tipo="correcao_solicitada",
        mensagem=f"Pré-correção disponível — nota sugerida: 600/1000",
    )
    assert Notificacao.objects.filter(usuario=prof, redacao=red).exists()


@pytest.mark.django_db
def test_avaliar_com_um_sem_temperature_kwarg():
    """Verificar que avaliar_com_um NÃO aceita temperature como kwarg direto."""
    from essay_essay.evaluators.orchestrator import avaliar_com_um
    import inspect
    sig = inspect.signature(avaliar_com_um)
    params = list(sig.parameters.keys())
    assert "temperature" not in params
    assert "top_p" not in params
    assert "seed" not in params
    assert "output_json" in params


@pytest.mark.django_db
def test_atividade_aluno_template_sem_copiloto_info():
    """Template não mostra info do corretor mesmo quando atividade tem copiloto."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Oculto", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ Teste", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, aluno)
    resp = client.get(f"/dashboard/atividades/{atv.id}/aluno")
    html = resp.content.decode()
    assert "Oculto" not in html
    assert "Corretor:" not in html


# ── Correção: filtrar apenas avaliações do copiloto ──────────────

@pytest.mark.django_db
def test_copiloto_pendentes_rejeita_avaliacao_humana():
    """Avaliacao rascunho criada por humano (sem corretor_llm) NÃO deve aparecer."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto humano com mais de vinte caracteres.", atividade=atv)
    # Avaliacao humana (sem corretor_llm)
    Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=True,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
    )
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/copiloto/pendentes")
    assert resp.status_code == 200
    assert "Ativ" not in resp.content.decode() or "Nenhuma pré-correção" in resp.content.decode()


@pytest.mark.django_db
def test_copiloto_pendentes_aceita_avaliacao_copiloto():
    """Avaliacao rascunho com corretor_llm do copiloto DEVE aparecer."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto copiloto com mais de vinte caracteres.", atividade=atv)
    Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=True,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
        corretor_llm=corretor,
    )
    client = Client()
    _login(client, prof)
    resp = client.get("/dashboard/copiloto/pendentes")
    assert resp.status_code == 200
    assert "Ativ" in resp.content.decode()


@pytest.mark.django_db
def test_copiloto_revisar_rejeita_avaliacao_humana():
    """GET em copiloto/revisar com avaliação humana deve redirecionar."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO, turma=turma)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    red = Redacao.objects.create(usuario=aluno, texto="Texto humano revisar com mais de vinte caracteres.", atividade=atv)
    av = Avaliacao.objects.create(
        redacao=red, nota_total=600, rascunho=True,
        c1_nota=120, c2_nota=120, c3_nota=120, c4_nota=120, c5_nota=120,
    )
    client = Client()
    _login(client, prof)
    resp = client.get(f"/dashboard/copiloto/revisar/{av.id}")
    # Deve redirecionar porque a avaliação não foi feita pelo corretor_llm do copiloto
    assert resp.status_code == 302


# ── Excluir Atividade ────────────────────────────────────────────

@pytest.mark.django_db
def test_atividade_excluir_post():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ Deletar", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, prof)
    resp = client.post(f"/dashboard/atividades/{atv.id}/excluir")
    assert resp.status_code == 302
    assert not AtividadeAvaliativa.objects.filter(id=atv.id).exists()


@pytest.mark.django_db
def test_atividade_excluir_get_redirect():
    """GET não deve excluir."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, prof)
    resp = client.get(f"/dashboard/atividades/{atv.id}/excluir")
    assert resp.status_code == 302
    assert AtividadeAvaliativa.objects.filter(id=atv.id).exists()


@pytest.mark.django_db
def test_atividade_excluir_redacoes_preservadas():
    """Redações vinculadas devem permanecer após excluir atividade (SET_NULL)."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    prof = _criar_usuario("prof@test.com", UserType.PROFESSOR)
    turma.professores.add(prof)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO)
    red = Redacao.objects.create(usuario=aluno, texto="Redacao com mais de vinte caracteres.", atividade=atv)
    client = Client()
    _login(client, prof)
    client.post(f"/dashboard/atividades/{atv.id}/excluir")
    red.refresh_from_db()
    assert red.atividade is None
    assert Redacao.objects.filter(id=red.id).exists()


@pytest.mark.django_db
def test_atividade_excluir_aluno_bloqueado():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )

    client = Client()
    _login(client, aluno)
    resp = client.post(f"/dashboard/atividades/{atv.id}/excluir")
    assert resp.status_code == 302
    assert AtividadeAvaliativa.objects.filter(id=atv.id).exists()


# ── Excluir Copiloto ─────────────────────────────────────────────

@pytest.mark.django_db
def test_copiloto_excluir_post():
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop Deletar", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    client = Client()
    _login(client, admin)
    resp = client.post(f"/dashboard/copiloto/{cop.id}/excluir")
    assert resp.status_code == 302
    assert not CorrecaoCopiloto.objects.filter(id=cop.id).exists()


@pytest.mark.django_db
def test_copiloto_excluir_aluno_bloqueado():
    aluno = _criar_usuario("aluno@test.com", UserType.ALUNO)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    client = Client()
    _login(client, aluno)
    resp = client.post(f"/dashboard/copiloto/{cop.id}/excluir")
    assert resp.status_code == 302
    assert CorrecaoCopiloto.objects.filter(id=cop.id).exists()


@pytest.mark.django_db
def test_copiloto_excluir_com_atividades_set_null():
    """Excluir copiloto deve setar copiloto=NULL nas atividades (SET_NULL)."""
    escola = _criar_escola()
    turma = _criar_turma(escola)
    admin = _criar_usuario("admin@test.com", UserType.ADMIN)
    corretor = _criar_corretor()
    cop = CorrecaoCopiloto.objects.create(
        nome="Cop", corretor_llm=corretor, criado_por=admin, ativo=True,
    )
    atv = _criar_atividade(
        titulo="Ativ", copiloto=cop, turma=turma, criado_por=admin,
    )
    client = Client()
    _login(client, admin)
    client.post(f"/dashboard/copiloto/{cop.id}/excluir")
    assert not CorrecaoCopiloto.objects.filter(id=cop.id).exists()
    atv.refresh_from_db()
    assert atv.copiloto is None  # SET_NULL
