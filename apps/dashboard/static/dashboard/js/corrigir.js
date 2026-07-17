'use strict';

window.CorrigirApp = (() => {
  const core = window.CorrigirCore;

  // ─── STATE ──────────────────────────────────────────────────────
  let state = {
    avaliacaoId: null,
    redacaoId: null,
    rascunhoCriado: false,
  };

  core.configure({
    onGetAvaliacaoId: () => state.avaliacaoId,
  });

  // ─── HELPERS ────────────────────────────────────────────────────
  function api(method, url, data) {
    return fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.getCSRFToken(),
      },
      body: data ? JSON.stringify(data) : undefined,
    }).then(r => r.json());
  }

  // ─── FORM ───────────────────────────────────────────────────────
  function salvarCompetencia(num) {
    const p = `c${num}_`;
    const data = { redacao_id: state.redacaoId };
    if (state.avaliacaoId) data.avaliacao_id = state.avaliacaoId;

    const notaEl = document.getElementById(`id_${p}nota`);
    data[`${p}nota`] = notaEl ? parseInt(notaEl.value) || null : null;
    data[`${p}justificativa`] = document.getElementById(`id_${p}justificativa`).value || '';
    data[`${p}sugestoes`] = document.getElementById(`id_${p}sugestoes`).value || '';

    core.mostrarStatus('Salvando...');
    api('POST', '/api/v1/avaliacoes/auto_salvar', data)
      .then(r => {
        if (r.avaliacao_id) {
          state.avaliacaoId = r.avaliacao_id;
          state.rascunhoCriado = true;
          document.getElementById('id_avaliacao_id').value = r.avaliacao_id;
          document.getElementById('btnFinalizar').disabled = false;
        }
        core.mostrarStatus('Salvo');
      })
      .catch(() => core.mostrarStatus('Erro'));

    marcarAvaliada(num, notaEl);
    avancarProxima(num);
  }

  function marcarAvaliada(num, notaEl) {
    const compEl = document.getElementById(`comp-${num}`);
    if (!compEl) return;
    compEl.classList.add('bg-success-subtle');
    setTimeout(() => compEl.classList.remove('bg-success-subtle'), 1200);

    const item = compEl.closest('.accordion-item');
    const notaVal = notaEl ? parseInt(notaEl.value) : -1;
    if (item && notaVal >= 0) {
      item.classList.replace('comp-nao-avaliada', 'comp-avaliada');
    }
  }

  function avancarProxima(num) {
    const next = Number(num) + 1;
    if (next <= 5) {
      const nextEl = document.getElementById(`comp-${next}`);
      if (!nextEl) return;
      bootstrap.Collapse.getOrCreateInstance(nextEl, { toggle: false }).show();
      setTimeout(() => {
        nextEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        nextEl.querySelector('input, textarea')?.focus();
      }, 350);
    } else {
      document.getElementById('btnFinalizar')
        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // ─── CARREGAR REDAÇÃO ──────────────────────────────────────────
  function selecionarRedacao(redacaoId, tema, aluno) {
    state.avaliacaoId = null;
    state.redacaoId = redacaoId;
    state.rascunhoCriado = false;
    core.reset();

    document.getElementById('id_redacao_id').value = redacaoId;
    document.getElementById('id_avaliacao_id').value = '';
    document.getElementById('temaSelecionado').textContent = `— ${tema}`;
    document.getElementById('alunoSelecionado').textContent = `Aluno: ${aluno}`;
    document.getElementById('btnFinalizar').disabled = true;
    core.mostrarStatus('');

    limparFormulario();
    resetarCompetencias();
    esconderTudo();

    document.getElementById('redacao-texto').innerHTML =
      '<div class="text-center py-4 text-muted">Carregando...</div>';

    api('POST', '/api/v1/avaliacoes/iniciar', { redacao_id: redacaoId, criar_rascunho: true })
      .then(onDadosCarregados)
      .catch(() => {
        document.getElementById('redacao-texto').innerHTML =
          '<div class="text-center py-4 text-danger">Erro ao carregar redação.</div>';
      });
  }

  function onDadosCarregados(data) {
    state.avaliacaoId = data.avaliacao_id;
    document.getElementById('id_avaliacao_id').value = data.avaliacao_id;

    renderizarTexto(data.redacao_texto);
    core.carregarAnotacoes();

    if (data.redacao_tema_ref_texto) {
      document.getElementById('tema-flutuante-conteudo').innerHTML = core.escHtml(data.redacao_tema_ref_texto);
      document.getElementById('btn-ver-tema').classList.remove('d-none');
    }

    if (data.tem_rascunho && data.avaliacao_id) {
      preencherRascunho(data.rascunho);
      state.rascunhoCriado = true;
      document.getElementById('btnFinalizar').disabled = false;
    }

    setTimeout(core.atualizarNotaTotal, 150);

    if (!document.getElementById('id_nome_avaliador').value) {
      document.getElementById('id_nome_avaliador').value =
        window.__CORRIGIR_CONFIG__?.nomeAvaliador || '';
    }
  }

  function limparFormulario() {
    document.getElementById('formAvaliacao')
      .querySelectorAll('input, textarea, select').forEach(el => {
        if (el.name && !['csrfmiddlewaretoken', 'redacao_id', 'avaliacao_id'].includes(el.name)) {
          el.value = '';
        }
      });
  }

  function resetarCompetencias() {
    document.querySelectorAll('.competencia-item.comp-avaliada').forEach(item => {
      item.classList.replace('comp-avaliada', 'comp-nao-avaliada');
    });
  }

  function esconderTudo() {
    document.getElementById('lista-anotacoes').style.display = 'none';
    document.getElementById('anotacao-contagem').style.display = 'none';
    document.getElementById('annotation-palette').style.display = 'none';
    document.getElementById('tema-flutuante')?.classList.add('d-none');
  }

  function renderizarTexto(texto) {
    document.getElementById('redacao-texto').innerHTML = core.escHtml(texto);
  }

  function preencherRascunho(dados) {
    if (!dados) return;
    for (const [campo, valor] of Object.entries(dados)) {
      const el = document.getElementById(`id_${campo}`);
      if (!el) continue;
      if (campo.endsWith('_nota') && (valor == null || valor === '' || valor === 0)) continue;
      el.value = valor;
    }
    for (let i = 1; i <= 5; i++) {
      const nota = dados[`c${i}_nota`];
      const item = document.getElementById(`comp-${i}`)?.closest('.accordion-item');
      if (item && nota != null && Number(nota) >= 0) {
        item.classList.replace('comp-nao-avaliada', 'comp-avaliada');
      }
    }
  }

  // ─── UI: Tema flutuante ────────────────────────────────────────
  function abrirTemaFlutuante() {
    document.getElementById('tema-flutuante')?.classList.remove('d-none');
  }

  function fecharTemaFlutuante() {
    document.getElementById('tema-flutuante')?.classList.add('d-none');
  }

  function initDrag() {
    const el = document.getElementById('tema-flutuante');
    const h = document.getElementById('tema-flutuante-header');
    if (!el || !h) return;

    let dragging = false, startX, startY, origLeft, origTop;

    h.addEventListener('mousedown', e => {
      e.preventDefault();
      dragging = true;
      startX = e.clientX;
      startY = e.clientY;
      origLeft = el.offsetLeft;
      origTop = el.offsetTop;
      el.style.right = 'auto';
      el.style.cursor = 'grabbing';
    });

    document.addEventListener('mousemove', e => {
      if (!dragging) return;
      el.style.left = `${origLeft + e.clientX - startX}px`;
      el.style.top = `${origTop + e.clientY - startY}px`;
    });

    document.addEventListener('mouseup', () => {
      dragging = false;
      el.style.cursor = '';
    });
  }

  // ─── INIT (corrigir-specific) ──────────────────────────────────
  function init() {
    if (!document.getElementById('formAvaliacao')) return;

    initDrag();
    core.atualizarNotaTotal();

    document.getElementById('accordionPendentes')
      ?.addEventListener('click', e => {
        const b = e.target.closest('[data-redacao-id]');
        if (b) selecionarRedacao(b.dataset.redacaoId, b.dataset.tema, b.dataset.aluno);
      });

    document.getElementById('accordionCompetencias')
      ?.addEventListener('click', e => {
        const b = e.target.closest('[data-competencia]');
        if (b) salvarCompetencia(b.dataset.competencia);
      });

    document.getElementById('anotacoes-container')
      ?.addEventListener('click', e => {
        const b = e.target.closest('[data-excluir-anotacao]');
        if (b) core.excluirAnotacao(b.dataset.excluirAnotacao);
      });

    document.addEventListener('click', e => {
      const acao = e.target.closest('[data-acao]')?.dataset.acao;
      if (acao === 'abrir-tema') abrirTemaFlutuante();
      if (acao === 'fechar-tema') fecharTemaFlutuante();
    });

    document.getElementById('formAvaliacao')
      ?.addEventListener('submit', () => { document.getElementById('btnFinalizar').disabled = true; });
  }

  document.addEventListener('DOMContentLoaded', init);

  // ─── EXPORTS (backward compat) ─────────────────────────────────
  return {
    salvarCompetencia,
    selecionarRedacao,
    abrirTemaFlutuante,
    fecharTemaFlutuante,
    handleTextSelect: core.handleTextSelect,
    confirmarAnotacao: core.confirmarAnotacao,
    cancelarAnotacao: core.cancelarAnotacao,
    fecharPaleta: core.fecharPaleta,
    excluirAnotacao: core.excluirAnotacao,
  };
})();
