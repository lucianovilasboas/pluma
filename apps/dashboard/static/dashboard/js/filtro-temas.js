'use strict';

window.FiltroTemas = (() => {

  function init(modo, opts) {
    opts = opts || {};
    if (modo === 'select') {
      initSelect(opts);
    } else if (modo === 'table') {
      initTable(opts);
    } else if (modo === 'combobox') {
      initCombobox(opts);
    }
  }

  // ─── Modo "select" (filtro externo + select) ────────────────

  function initSelect(opts) {
    var input = document.getElementById(opts.inputId || 'filtro-temas');
    var select = document.getElementById(opts.selectId || 'select-tema');
    var msgVazio = document.getElementById(opts.msgVazioId || 'filtro-sem-resultados');
    if (!input || !select) return;

    input.addEventListener('input', function () {
      var busca = input.value.toLowerCase();
      var opt = select.options;
      var count = 0;

      for (var i = 0; i < opt.length; i++) {
        var data = opt[i].getAttribute('data-busca') || opt[i].text.toLowerCase();
        var match = data.includes(busca) || busca === '';
        opt[i].style.display = match ? '' : 'none';
        if (match) count++;
      }

      if (select.selectedOptions.length > 0
          && select.selectedOptions[0].style.display === 'none') {
        select.value = '';
        if (opts.onChange) opts.onChange(select);
      }

      if (msgVazio) {
        msgVazio.style.display = (count === 0 && busca !== '') ? '' : 'none';
      }
    });
  }

  // ─── Modo "table" (filtro de linhas em tabela) ──────────────

  function initTable(opts) {
    var input = document.getElementById(opts.inputId || 'busca-temas');
    var rows = document.querySelectorAll(opts.rowSelector || '.tema-row');
    if (!input || !rows.length) return;

    input.addEventListener('input', function () {
      var busca = input.value.toLowerCase();
      for (var i = 0; i < rows.length; i++) {
        var text = rows[i].getAttribute('data-search') || '';
        rows[i].style.display = text.includes(busca) ? '' : 'none';
      }
    });
  }

  // ─── Modo "combobox" (input + dropdown integrados) ──────────

  function initCombobox(opts) {
    var select = document.getElementById(opts.selectId || 'select-tema');
    if (!select) return;

    select.style.display = 'none';

    var wrapper = document.createElement('div');
    wrapper.className = 'position-relative mb-3';
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control';
    input.placeholder = '\uD83D\uDD0D Buscar ou selecionar tema...';
    input.autocomplete = 'off';
    wrapper.insertBefore(input, select);

    var dropdown = document.createElement('div');
    dropdown.className = 'position-absolute w-100 bg-white border rounded shadow-sm d-none';
    dropdown.style.cssText = 'z-index:1050;max-height:250px;overflow-y:auto;';
    wrapper.appendChild(dropdown);

    function selecionar(optEl) {
      select.value = optEl.value;
      input.value = optEl.text;
      dropdown.classList.add('d-none');
      if (opts.onChange) opts.onChange(select);
    }

    function montarLista(busca) {
      busca = (busca || '').toLowerCase();
      dropdown.innerHTML = '';
      var opt = select.options;
      var count = 0;

      for (var i = 0; i < opt.length; i++) {
        var data = opt[i].getAttribute('data-busca') || opt[i].text.toLowerCase();
        if (!data.includes(busca)) continue;
        count++;

        var item = document.createElement('div');
        item.className = 'dropdown-item px-3 py-2';
        item.style.cursor = 'pointer';
        item.textContent = opt[i].text;
        item.addEventListener('click', (function(el) {
          return function () { selecionar(el); };
        })(opt[i]));
        dropdown.appendChild(item);
      }

      if (count === 0 && busca !== '') {
        var vazio = document.createElement('div');
        vazio.className = 'px-3 py-2 text-muted small';
        vazio.textContent = 'Nenhum tema encontrado.';
        dropdown.appendChild(vazio);
      }

      dropdown.classList.toggle('d-none', count === 0 && busca === '');
    }

    input.addEventListener('input', function () {
      montarLista(input.value);
    });

    input.addEventListener('focus', function () {
      var self = this;
      setTimeout(function () { self.select(); }, 0);
      montarLista(input.value);
    });

    input.addEventListener('click', function () {
      this.select();
      montarLista(this.value);
    });

    input.addEventListener('blur', function () {
      setTimeout(function () { dropdown.classList.add('d-none'); }, 200);
    });

    if (select.selectedIndex > 0) {
      input.value = select.options[select.selectedIndex].text;
    }
  }

  return { init: init };
})();
