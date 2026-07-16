(function () {
  'use strict';

  document.querySelectorAll('.feedback-section').forEach(function (section) {
    var url = section.dataset.url;
    var badge = section.querySelector('.feedback-badge');
    var ratingSpan = section.querySelector('.feedback-rating');

    section.querySelectorAll('.feedback-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var valor = this.dataset.valor;
        var btnBom = section.querySelector('[data-valor="bom"]');
        var btnRuim = section.querySelector('[data-valor="ruim"]');

        fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
          },
          body: JSON.stringify({ valor: valor }),
        })
          .then(function (r) {
            if (!r.ok) return r.json().then(function (e) { throw new Error(e.erro || 'erro ' + r.status); });
            return r.json();
          })
          .then(function (data) {
            var baseBom = 'btn btn-sm feedback-btn py-0';
            var baseRuim = 'btn btn-sm feedback-btn py-0';

            if (data.admin_feedback === 'bom') {
              badge.innerHTML = '<span class="badge bg-success">👍</span>';
              btnBom.className = baseBom + ' btn-success';
              btnRuim.className = baseRuim + ' btn-outline-danger';
            } else if (data.admin_feedback === 'ruim') {
              badge.innerHTML = '<span class="badge bg-danger">👎</span>';
              btnBom.className = baseBom + ' btn-outline-success';
              btnRuim.className = baseRuim + ' btn-danger';
            } else {
              badge.innerHTML = '';
              btnBom.className = baseBom + ' btn-outline-success';
              btnRuim.className = baseRuim + ' btn-outline-danger';
            }

            if (data.rating !== null && data.rating !== undefined) {
              ratingSpan.textContent = '⭐ ' + (data.corretor_nome || '') + ' ' + data.rating;
              ratingSpan.style.display = '';
            }
          })
          .catch(function (err) {
            mostrarToast('Erro ao salvar feedback: ' + err.message, 'erro');
          });
      });
    });
  });
})();
