'use strict';

window.BannerCorrigida = (() => {
  var STORAGE_KEY = 'banner_corrigida_ultimo_id';

  function jaVisto(id) {
    try { return localStorage.getItem(STORAGE_KEY) === id; } catch { return false; }
  }

  function marcarVisto(id) {
    try { localStorage.setItem(STORAGE_KEY, id); } catch {}
  }

  function injectStyles() {
    if (document.getElementById('banner-corrigida-estilos')) return;
    var style = document.createElement('style');
    style.id = 'banner-corrigida-estilos';
    style.textContent = [
      '@keyframes bannerSlideDown {',
      '  from { opacity: 0; transform: translateY(-20px); }',
      '  to   { opacity: 1; transform: translateY(0); }',
      '}',
      '@keyframes bannerPulse {',
      '  0%, 100% { box-shadow: 0 0 0 0 rgba(25, 135, 84, 0.4); }',
      '  50%      { box-shadow: 0 0 20px 8px rgba(25, 135, 84, 0.15); }',
      '}',
      '#banner-corrigida {',
      '  animation: bannerSlideDown 0.4s ease-out, bannerPulse 2s ease-in-out 3;',
      '}',
    ].join('\n');
    document.head.appendChild(style);
  }

  function criarBanner(data) {
    var banner = document.createElement('div');
    banner.id = 'banner-corrigida';
    banner.className = 'alert alert-success border-success border-2 mb-4';
    banner.innerHTML = [
      '<div class="d-flex align-items-center gap-3">',
      '  <span style="font-size: 2rem">\u2705</span>',
      '  <div class="flex-grow-1">',
      '    <strong class="fs-5">Corre\u00e7\u00e3o conclu\u00edda!</strong><br>',
      '    Sua reda\u00e7\u00e3o "' + escHtml(data.tema) + '" recebeu nota',
      '    <strong>' + data.nota + '/1000</strong>.',
      '  </div>',
      '  <a href="/dashboard/redacao/' + data.id + '"',
      '     class="btn btn-success btn-sm" data-dispensar>Ver detalhes</a>',
      '  <button class="btn btn-outline-secondary btn-sm" data-dispensar>Dispensar</button>',
      '</div>',
    ].join('');

    var botoes = banner.querySelectorAll('[data-dispensar]');
    for (var i = 0; i < botoes.length; i++) {
      botoes[i].addEventListener('click', function () {
        marcarVisto(data.id);
        banner.remove();
      });
    }

    return banner;
  }

  function escHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str || ''));
    return div.innerHTML;
  }

  function mostrar() {
    injectStyles();

    fetch('/dashboard/api/ultima-corrigida', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.tem_ultima || jaVisto(data.id)) return;

        var banner = criarBanner(data);
        var container = document.querySelector('nav + .h3 + .d-flex');
        if (container) {
          container.parentNode.insertBefore(banner, container.nextSibling);
        }

        setTimeout(function () {
          banner.style.animation = '';
        }, 10000);
      })
      .catch(function () {});
  }

  function init() {
    injectStyles();
    mostrar();
  }

  return { init: init, mostrar: mostrar };
})();
