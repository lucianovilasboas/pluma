'use strict';

window.EditarCorrecaoApp = (() => {
  const core = window.CorrigirCore;

  // ─── STATE ──────────────────────────────────────────────────────
  let _timerAutoSave = null;

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

  function getFormData() {
    const data = {};
    document.querySelectorAll('#formEdicao input, #formEdicao textarea').forEach(el => {
      if (el.name && el.type !== 'hidden') {
        data[el.name] = el.value;
      }
    });
    const rf = document.getElementById('id_redacao_id');
    const av = document.getElementById('id_avaliacao_id');
    if (rf) data.redacao_id = rf.value;
    if (av) data.avaliacao_id = av.value;
    return data;
  }

  // ─── AUTO-SAVE ─────────────────────────────────────────────────
  function autoSalvar() {
    const data = getFormData();

    core.mostrarStatus('Salvando...');
    clearTimeout(_timerAutoSave);

    api('POST', '/api/v1/avaliacoes/auto_salvar', data)
      .then(r => {
        if (r.avaliacao_id) {
          const av = document.getElementById('id_avaliacao_id');
          if (av) av.value = r.avaliacao_id;
        }
        core.mostrarStatus('Salvo');
      })
      .catch(() => core.mostrarStatus('Erro'));
  }

  function agendarAutoSalvar() {
    clearTimeout(_timerAutoSave);
    _timerAutoSave = setTimeout(autoSalvar, 2000);
  }

  // ─── COMPETÊNCIAS ──────────────────────────────────────────────
  function salvarCompetencia(num) {
    const btn = document.querySelector(`[data-competencia="${num}"]`);
    if (btn) {
      btn.classList.add('bg-light');
      setTimeout(() => btn.classList.remove('bg-light'), 600);
    }
    autoSalvar();
  }

  // ─── INIT ───────────────────────────────────────────────────────
  function init() {
    if (!document.getElementById('formEdicao')) return;

    const cfg = window.__EDITAR_CONFIG__;
    if (cfg) {
      core.configure({
        onGetAvaliacaoId: () => cfg.avaliacaoId,
        anotacoes: cfg.anotacoes,
      });
      core.aplicarRealces();
      core.renderizarLista();
    }

    core.atualizarNotaTotal();

    document.getElementById('formEdicao')
      ?.addEventListener('input', agendarAutoSalvar);

    document.getElementById('accordionCompetencias')
      ?.addEventListener('click', e => {
        const b = e.target.closest('[data-competencia]');
        if (b) salvarCompetencia(b.dataset.competencia);
      });

    document.getElementById('anotacoes-container')
      ?.addEventListener('click', e => {
        const b = e.target.closest('[data-excluir-anotacao]');
        if (b && confirm('Remover esta anotação?')) core.excluirAnotacao(b.dataset.excluirAnotacao);
      });

    document.addEventListener('click', e => {
      const b = e.target.closest('[data-acao]');
      if (!b) return;
      const acao = b.dataset.acao;
      if (acao === 'toggle-tema-conteudo') {
        const el = b.nextElementSibling;
        if (el) el.classList.toggle('d-none');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', init);

  return {
    salvarCompetencia,
    autoSalvar,
  };
})();
