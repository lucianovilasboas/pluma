var DashboardBancas = (function() {
  'use strict';

  function getCSRFToken() {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      var c = cookies[i].trim();
      if (c.startsWith('csrftoken=')) return c.substring(10);
    }
    return '';
  }

  function api(method, url, body) {
    var opts = {
      method: method,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
      credentials: 'include',
    };
    if (body) opts.body = JSON.stringify(body);
    return fetch(url, opts).then(function(r) {
      if (!r.ok) {
        return r.json().then(function(err) {
          throw new Error(err.detail || r.status + ' ' + r.statusText);
        }).catch(function() {
          throw new Error(r.status + ' ' + r.statusText);
        });
      }
      var ct = r.headers.get('content-type') || '';
      if (ct.includes('application/json')) return r.json();
      return null;
    });
  }

  function setStatusLabel(id, ativo) {
    var label = document.querySelector('label[for="switch-' + id + '"]');
    if (label) label.textContent = ativo ? 'Ativo' : 'Inativo';
  }

  function toggle(id, checked) {
    var endpoint = checked
      ? '/api/v1/admin/pools/' + id + '/ativar'
      : '/api/v1/admin/pools/' + id + '/desativar';
    var sw = document.getElementById('switch-' + id);
    if (sw) sw.disabled = true;
    fetch(endpoint, { method: 'POST', headers: { 'X-CSRFToken': getCSRFToken() } })
      .then(function(r) {
        if (!r.ok) {
          if (sw) { sw.checked = !checked; sw.disabled = false; setStatusLabel(id, !checked); }
          throw new Error('Erro');
        }
        setStatusLabel(id, checked);
        if (sw) sw.disabled = false;
      })
      .catch(function(e) {
        if (sw) { sw.checked = !checked; sw.disabled = false; setStatusLabel(id, !checked); }
        alert('Erro ao alterar status: ' + e.message);
      });
  }

  function abrirModal(id, nome, metodo, ordem, limite) {
    document.getElementById('banca-id').value = id || '';
    document.getElementById('banca-nome').value = nome || '';
    document.getElementById('banca-ordem').value = ordem != null ? ordem : 0;
    document.getElementById('banca-limite-concorrencia').value = limite != null ? limite : 10;
    document.getElementById('banca-metodo').value = metodo || 'mediana';
    document.getElementById('banca-descricao').value = '';
    document.getElementById('banca-limiar').value = '20';
    document.getElementById('banca-revisor').value = '';
    document.getElementById('banca-modo').value = 'pool';
    document.getElementById('banca-provedor').value = '';
    document.getElementById('banca-modelo-llm').value = '';
    toggleModoEspecialistas();
    if (id) {
      api('GET', '/api/v1/admin/pools/' + id).then(function(data) {
        document.getElementById('banca-descricao').value = data.descricao || '';
        document.getElementById('banca-ordem').value = data.ordem != null ? data.ordem : 0;
        document.getElementById('banca-limite-concorrencia').value = data.limite_concorrencia != null ? data.limite_concorrencia : 10;
        document.getElementById('banca-limiar').value = data.limiar_desvio != null ? data.limiar_desvio : 20;
        document.getElementById('banca-revisor').value = data.revisor_corretor || '';
        document.getElementById('banca-modo').value = data.modo || 'pool';
        document.getElementById('banca-provedor').value = data.provedor || '';
        document.getElementById('banca-modelo-llm').value = data.modelo_llm || '';
        toggleModoEspecialistas();
      }).catch(function() {});
    }
    document.getElementById('modal-banca-titulo').textContent = id ? 'Editar Banca' : 'Nova Banca';
    var el = document.getElementById('modal-banca');
    var modal = bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el);
    modal.show();
  }

  function salvar(e) {
    e.preventDefault();
    var id = document.getElementById('banca-id').value;
    var modo = document.getElementById('banca-modo').value || 'pool';
    var limiarVal = parseFloat(document.getElementById('banca-limiar').value);
    var ordemVal = parseInt(document.getElementById('banca-ordem').value, 10);
    var limiteVal = parseInt(document.getElementById('banca-limite-concorrencia').value, 10);
    var data = {
      nome: document.getElementById('banca-nome').value,
      ordem: isNaN(ordemVal) ? 0 : ordemVal,
      limite_concorrencia: isNaN(limiteVal) ? 10 : limiteVal,
      metodo: document.getElementById('banca-metodo').value,
      descricao: document.getElementById('banca-descricao').value,
      limiar_desvio: isNaN(limiarVal) ? 20 : limiarVal,
      revisor_corretor: document.getElementById('banca-revisor').value || null,
      modo: modo,
      provedor: document.getElementById('banca-provedor').value || null,
      modelo_llm: document.getElementById('banca-modelo-llm').value || '',
    };

    var confirmar = function() { return Promise.resolve(); };
    if (id && modo === 'especialistas') {
      confirmar = function() {
        return api('GET', '/api/v1/admin/pools/' + id).then(function(pool) {
          var qtd = (pool.corretores || []).length;
          if (qtd > 0) {
            return new Promise(function(resolve, reject) {
              var ok = confirm(
                'Atenção: esta banca possui ' + qtd + ' avaliador(es). '
                + 'No modo Especialistas, os avaliadores individuais não são utilizados.\n\n'
                + 'Ao salvar, todos os avaliadores serão removidos automaticamente.\n\n'
                + 'Deseja continuar?'
              );
              if (ok) resolve(); else reject(new Error('cancel'));
            });
          }
        });
      };
    }

    var url = id ? '/api/v1/admin/pools/' + id : '/api/v1/admin/pools';
    var btn = document.querySelector('#modal-banca button[type="submit"]');
    confirmar().then(function() {
      if (btn) btn.disabled = true;
      return api(id ? 'PUT' : 'POST', url, data);
    }).then(function() { location.reload(); })
      .catch(function(e) {
        if (btn) btn.disabled = false;
        if (e.message !== 'cancel') alert('Erro ao salvar: ' + e.message);
      });
  }

  function toggleModoEspecialistas() {
    var modo = document.getElementById('banca-modo').value;
    var campos = document.getElementById('especialistas-campos');
    if (campos) {
      campos.style.display = modo === 'especialistas' ? '' : 'none';
    }
  }

  function excluir(id, nome) {
    if (!confirm('Excluir a banca "' + nome + '" permanentemente?')) return;
    api('DELETE', '/api/v1/admin/pools/' + id).then(function() { location.reload(); })
      .catch(function(e) { alert('Erro ao excluir: ' + e.message); });
  }

  return { toggle: toggle, abrirModal: abrirModal, salvar: salvar, excluir: excluir };
})();
