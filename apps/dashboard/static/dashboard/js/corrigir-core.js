'use strict';

window.CorrigirCore = (() => {
  // ─── CONSTANTS ──────────────────────────────────────────────────
  const MAX_ANOTACOES = 30;
  const CAMPO_NOTA = ['c1_nota', 'c2_nota', 'c3_nota', 'c4_nota', 'c5_nota'];

  const TIPO = {
    cores: { ortografia: '#ef4444', concordancia: '#f97316', pontuacao: '#eab308',
             coesao: '#a855f7', vocabulario: '#3b82f6', argumentacao: '#ec4899',
             clareza: '#22c55e', outro: '#94a3b8' },
    labels: { ortografia: 'Ortografia', concordancia: 'Concordância', pontuacao: 'Pontuação',
              coesao: 'Coesão', vocabulario: 'Vocabulário', argumentacao: 'Argumentação',
              clareza: 'Clareza', outro: 'Outro' },
    ordem: ['ortografia', 'concordancia', 'pontuacao', 'coesao', 'vocabulario',
            'argumentacao', 'clareza', 'outro'],
  };

  // ─── STATE ──────────────────────────────────────────────────────
  let state = {
    anotacoes: [],
    selectedRange: null,
    selectedTipo: null,
  };

  let _getAvaliacaoId = () => null;

  // ─── HELPERS ────────────────────────────────────────────────────
  function getCSRFToken() {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const c = cookies[i].trim();
      if (c.startsWith('csrftoken=')) return c.substring(10);
    }
    return '';
  }

  const escHtml = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const escAttr = s => escHtml(s).replace(/"/g, '&quot;');

  function api(method, url, data) {
    return fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
      },
      body: data ? JSON.stringify(data) : undefined,
    }).then(r => {
      if (r.status === 204) return null;
      if (!r.ok) return r.json().then(e => Promise.reject(e));
      return r.json();
    });
  }

  function mostrarStatus(texto) {
    const el = document.getElementById('autoSaveStatus');
    if (!el) return;
    el.textContent = texto;
    el.style.opacity = '1';
    if (texto === 'Salvo') setTimeout(() => { el.style.opacity = '0'; }, 2000);
  }

  function offsetAbsoluto(container, node, offset) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    let total = 0;
    while (walker.nextNode()) {
      const tn = walker.currentNode;
      if (tn === node) return total + offset;
      total += tn.textContent.length;
    }
    if (container === node) return offset;
    return null;
  }

  // ─── ANOTAÇÕES: Seleção ────────────────────────────────────────
  function handleTextSelect() {
    if (state.anotacoes.length >= MAX_ANOTACOES) return;

    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount || sel.toString().trim() === '') {
      fecharPaleta();
      return;
    }

    const container = document.getElementById('redacao-texto');
    const range = sel.getRangeAt(0);
    const textoCompleto = container.textContent;
    const inicio = offsetAbsoluto(container, range.startContainer, range.startOffset);
    const fim = offsetAbsoluto(container, range.endContainer, range.endOffset);
    if (inicio == null || fim == null || inicio >= fim) return;

    const raw = textoCompleto.substring(inicio, fim);
    const trecho = raw.trim();
    if (!trecho.length) return;

    const leading = raw.length - raw.trimStart().length;
    const trailing = raw.length - raw.trimEnd().length;
    state.selectedRange = { inicio: inicio + leading, fim: fim - trailing, texto: trecho };

    construirPaleta();
    document.getElementById('annotation-palette').style.display = 'flex';
    posicionarPaleta();
  }

  // ─── ANOTAÇÕES: Paleta ─────────────────────────────────────────
  function construirPaleta() {
    const pal = document.getElementById('annotation-palette');
    pal.innerHTML = '';
    const counts = contarTipos();

    for (const t of TIPO.ordem) {
      const dot = document.createElement('span');
      dot.className = 'palette-dot';
      dot.dataset.tipo = t;
      dot.style.background = TIPO.cores[t];
      dot.style.color = TIPO.cores[t];
      dot.addEventListener('click', () => selecionarTipo(t));

      const tip = document.createElement('span');
      tip.className = 'dot-tooltip';
      tip.textContent = TIPO.labels[t];
      dot.appendChild(tip);

      const cnt = document.createElement('span');
      cnt.className = 'palette-count';
      cnt.id = `pc-${t}`;
      cnt.textContent = counts[t] || 0;
      dot.appendChild(cnt);
      pal.appendChild(dot);
    }

    const sep = document.createElement('span');
    sep.className = 'palette-divider';
    pal.appendChild(sep);

    const fechar = document.createElement('button');
    fechar.className = 'palette-done';
    fechar.textContent = '\u2713';
    fechar.onclick = fecharPaleta;
    pal.appendChild(fechar);

    const area = document.createElement('div');
    area.className = 'palette-input-area';
    area.id = 'palette-input-area';

    const inp = document.createElement('input');
    inp.className = 'palette-input';
    inp.id = 'palette-comment';
    inp.type = 'text';
    inp.maxLength = 80;
    inp.placeholder = 'Comentário (opcional)...';
    inp.onkeydown = e => { if (e.key === 'Enter') confirmarAnotacao(); };
    area.appendChild(inp);

    const salvar = document.createElement('button');
    salvar.className = 'palette-btn-save';
    salvar.textContent = 'Salvar';
    salvar.onclick = confirmarAnotacao;
    area.appendChild(salvar);

    const cancelar = document.createElement('button');
    cancelar.className = 'palette-btn-cancel';
    cancelar.textContent = 'Cancelar';
    cancelar.onclick = cancelarAnotacao;
    area.appendChild(cancelar);

    pal.appendChild(area);
  }

  function contarTipos() {
    const c = {};
    for (const t of TIPO.ordem) c[t] = 0;
    for (const a of state.anotacoes) if (a.tipo_erro in c) c[a.tipo_erro]++;
    return c;
  }

  function atualizarContagens() {
    const c = contarTipos();
    for (const t of TIPO.ordem) {
      const el = document.getElementById(`pc-${t}`);
      if (el) el.textContent = c[t] || 0;
    }
  }

  function posicionarPaleta() {
    if (!state.selectedRange) return;
    const sel = window.getSelection();
    if (!sel.rangeCount) return;
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    const pal = document.getElementById('annotation-palette');

    let top = rect.top - pal.offsetHeight - 8;
    if (top < 4) top = rect.bottom + 4;

    let left = rect.left + rect.width / 2 - pal.offsetWidth / 2;
    if (left < 4) left = 4;
    if (left + pal.offsetWidth > window.innerWidth - 4) left = window.innerWidth - pal.offsetWidth - 4;

    pal.style.top = `${top}px`;
    pal.style.left = `${left}px`;
  }

  function selecionarTipo(tipo) {
    document.querySelectorAll('#annotation-palette .palette-dot')
      .forEach(d => d.classList.remove('selected'));
    document.querySelector(`#annotation-palette .palette-dot[data-tipo="${tipo}"]`)
      ?.classList.add('selected');
    state.selectedTipo = tipo;
    document.getElementById('palette-input-area').classList.add('visible');
    document.getElementById('palette-comment').focus();
  }

  function confirmarAnotacao() {
    if (!state.selectedTipo) return;
    const inp = document.getElementById('palette-comment');
    criarAnotacaoDoTipo(state.selectedTipo, inp.value);
    inp.value = '';
    fecharPaleta();
  }

  function cancelarAnotacao() {
    state.selectedTipo = null;
    document.querySelectorAll('#annotation-palette .palette-dot')
      .forEach(d => d.classList.remove('selected'));
    document.getElementById('palette-input-area')?.classList.remove('visible');
  }

  function fecharPaleta() {
    cancelarAnotacao();
    const pal = document.getElementById('annotation-palette');
    if (pal) pal.style.display = 'none';
    state.selectedRange = null;
    window.getSelection()?.removeAllRanges();
  }

  // ─── ANOTAÇÕES: CRUD ───────────────────────────────────────────
  function criarAnotacaoDoTipo(tipo, comentario) {
    const avaliacaoId = _getAvaliacaoId();
    if (!state.selectedRange || !avaliacaoId) return;
    if (state.anotacoes.length >= MAX_ANOTACOES) return;

    api('POST', '/api/v1/anotacoes', {
      avaliacao: avaliacaoId,
      trecho_inicio: state.selectedRange.inicio,
      trecho_fim: state.selectedRange.fim,
      trecho_texto: state.selectedRange.texto,
      tipo_erro: tipo,
      comentario: comentario || '',
    }).then(data => {
      if (!data.id) return;
      state.anotacoes.push(data);
      aplicarRealces();
      renderizarLista();
      atualizarContagens();
    }).catch(() => alert('Erro ao salvar anotação.'));
  }

  function carregarAnotacoes() {
    const avaliacaoId = _getAvaliacaoId();
    if (!avaliacaoId) return;
    api('GET', `/api/v1/anotacoes?avaliacao_id=${avaliacaoId}`)
      .then(data => {
        state.anotacoes = Array.isArray(data) ? data : (data.results || []);
        aplicarRealces();
        renderizarLista();
      });
  }

  function excluirAnotacao(id) {
    api('DELETE', `/api/v1/anotacoes/${id}`)
      .then(() => {
        state.anotacoes = state.anotacoes.filter(a => a.id !== id);
        aplicarRealces();
        renderizarLista();
        atualizarContagens();
      })
      .catch(() => {});
  }

  // ─── ANOTAÇÕES: Lista ──────────────────────────────────────────
  function renderizarLista() {
    const container = document.getElementById('anotacoes-container');
    const cnt = document.getElementById('anotacao-contagem');
    const lista = document.getElementById('lista-anotacoes');
    if (!container) return;

    if (!state.anotacoes.length) {
      if (lista) lista.style.display = 'none';
      if (cnt) cnt.style.display = 'none';
      return;
    }

    if (lista) lista.style.display = 'block';
    if (cnt) {
      cnt.style.display = 'inline';
      cnt.textContent = `${state.anotacoes.length}/${MAX_ANOTACOES} anotação${state.anotacoes.length > 1 ? 'ões' : ''}`;
    }

    container.innerHTML = state.anotacoes.map(a => {
      const cor = TIPO.cores[a.tipo_erro] || '#94a3b8';
      const label = TIPO.labels[a.tipo_erro] || a.tipo_erro;
      const snippet = escHtml(a.trecho_texto.substring(0, 40)) + (a.trecho_texto.length > 40 ? '...' : '');
      const coment = a.comentario
        ? `<div class="small text-muted mt-1">${escHtml(a.comentario)}</div>`
        : '';
      return `<div class="anotacao-item py-1">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <span class="badge rounded-pill small" style="background:${cor};color:#fff;">${label}</span>
            <span class="small ms-2 text-muted">"${snippet}"</span>
          </div>
          <button type="button" class="btn btn-sm text-danger border-0" data-excluir-anotacao="${a.id}" title="Remover">&times;</button>
        </div>
        ${coment}
      </div>`;
    }).join('');
  }

  // ─── ANOTAÇÕES: Highlights ─────────────────────────────────────
  function aplicarRealces() {
    if (!state.anotacoes.length) {
      const container = document.getElementById('redacao-texto');
      if (container) container.innerHTML = escHtml(container.textContent);
      return;
    }

    const sorted = [...state.anotacoes].sort((a, b) => a.trecho_inicio - b.trecho_inicio);
    const container = document.getElementById('redacao-texto');
    if (!container) return;
    const texto = container.textContent;

    const bounds = { 0: true, [texto.length]: true };
    for (const a of sorted) { bounds[a.trecho_inicio] = true; bounds[a.trecho_fim] = true; }
    const points = Object.keys(bounds).map(Number).sort((a, b) => a - b);

    const partes = [];
    for (let i = 0; i < points.length - 1; i++) {
      const inicio = points[i];
      const fim = points[i + 1];
      if (inicio >= fim) continue;

      const seg = texto.substring(inicio, fim);
      const cover = sorted.filter(a => a.trecho_inicio <= inicio && a.trecho_fim >= fim);

      if (!cover.length) {
        partes.push(escHtml(seg));
        continue;
      }

      const tipos = [...new Set(cover.map(a => a.tipo_erro))];
      const anns = cover.map(a => ({
        tipo: a.tipo_erro,
        label: TIPO.labels[a.tipo_erro] || a.tipo_erro,
        comentario: a.comentario || '',
      }));

      partes.push(
        `<span class="${tipos.map(t => 'anotacao-' + t).join(' ')}" style="${styleRealce(tipos)}" data-anotacoes="${escAttr(JSON.stringify(anns))}">${escHtml(seg)}</span>`
      );
    }
    container.innerHTML = partes.join('');
  }

  function styleRealce(tipos) {
    const shadows = [];
    const bgs = [];
    for (let i = 0; i < tipos.length; i++) {
      const cor = TIPO.cores[tipos[i]] || '#94a3b8';
      shadows.push(`inset ${3 + i * 3}px 0 0 0 ${cor}`);
      const r = parseInt(cor.slice(1, 3), 16);
      const g = parseInt(cor.slice(3, 5), 16);
      const b = parseInt(cor.slice(5, 7), 16);
      bgs.push(`rgba(${r},${g},${b},0.10)`);
    }
    const bg = bgs.length ? `linear-gradient(90deg, ${bgs.join(',')})` : 'transparent';
    return [
      `box-shadow:${shadows.join(',')}`,
      `background:${bg}`,
      `padding-left:${ tipos.length * 3 }px`,
      'border-radius:3px;cursor:help;display:inline;',
    ].join(';');
  }

  // ─── ANOTAÇÕES: Tooltip ────────────────────────────────────────
  function mostrarTooltip(e, anns) {
    const tip = document.getElementById('annotation-tooltip');
    tip.innerHTML = anns.map(a => {
      const cor = TIPO.cores[a.tipo] || '#94a3b8';
      return `<div class="tt-item"><span class="tt-dot" style="background:${cor}"></span><strong>${escHtml(a.label)}</strong>${a.comentario ? ': ' + escHtml(a.comentario) : ''}</div>`;
    }).join('');

    let x = e.clientX + 12;
    let y = e.clientY - 8;
    if (x + 320 > window.innerWidth) x = e.clientX - 320 - 4;
    if (y < 4) y = e.clientY + 8;

    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
    tip.classList.add('visible');
  }

  function esconderTooltip() {
    document.getElementById('annotation-tooltip').classList.remove('visible');
  }

  // ─── UI ─────────────────────────────────────────────────────────
  function atualizarNotaTotal() {
    let total = 0;
    for (const nome of CAMPO_NOTA) {
      const el = document.getElementById(`id_${nome}`);
      if (!el) continue;
      const v = parseInt(el.value);
      if (!isNaN(v) && v >= 0) total += v;
    }
    const display = document.getElementById('nota-total-display');
    if (display) display.textContent = total;
  }

  // ─── INIT ───────────────────────────────────────────────────────
  function init() {
    if (document.getElementById('annotation-palette')) {
      document.getElementById('redacao-texto')
        ?.addEventListener('mouseup', handleTextSelect);
    }

    document.addEventListener('click', e => {
      if (!e.target.closest('#annotation-palette, #redacao-texto')) fecharPaleta();
    });

    document.addEventListener('mouseover', e => {
      const s = e.target.closest('span[data-anotacoes]');
      if (s) try { mostrarTooltip(e, JSON.parse(s.dataset.anotacoes)); } catch (_) {}
    });

    document.addEventListener('mouseout', e => {
      if (e.target.closest('span[data-anotacoes]')) esconderTooltip();
    });

    document.querySelectorAll('[id^="id_c"][id$="_nota"]')
      .forEach(el => el.addEventListener('input', atualizarNotaTotal));
  }

  document.addEventListener('DOMContentLoaded', init);

  // ─── RESET ──────────────────────────────────────────────────────
  function reset() {
    state.anotacoes = [];
    state.selectedRange = null;
    state.selectedTipo = null;
  }

  // ─── CONFIG ─────────────────────────────────────────────────────
  function configure(opts) {
    if (opts) {
      if (opts.onGetAvaliacaoId) _getAvaliacaoId = opts.onGetAvaliacaoId;
      if (opts.anotacoes) state.anotacoes = opts.anotacoes;
    }
  }

  // ─── EXPORTS ────────────────────────────────────────────────────
  return {
    MAX_ANOTACOES, CAMPO_NOTA, TIPO,
    state,
    api, escHtml, escAttr,
    handleTextSelect, construirPaleta, posicionarPaleta,
    selecionarTipo, confirmarAnotacao, cancelarAnotacao, fecharPaleta,
    criarAnotacaoDoTipo, carregarAnotacoes, excluirAnotacao,
    aplicarRealces, styleRealce, renderizarLista, contarTipos, atualizarContagens,
    mostrarTooltip, esconderTooltip,
    atualizarNotaTotal, mostrarStatus,
    reset, configure,
  };
})();
