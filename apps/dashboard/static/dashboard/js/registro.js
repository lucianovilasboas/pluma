'use strict';

window.RegistroApp = (() => {
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var VERIFY_URL = '/api/v1/auth/verificar-email';

  var emailCheckTimer = null;
  var emailCheckLastValue = '';

  function init() {
    initServerErrors();
    initClearServerErrorsOnInput();
    initPasswordMatch();
    initEmailCheck();
    initFormSubmit();
  }

  function initClearServerErrorsOnInput() {
    var form = document.querySelector('form');
    if (!form) return;
    var inputs = form.querySelectorAll('input, select, textarea');
    for (var i = 0; i < inputs.length; i++) {
      inputs[i].addEventListener('input', function () {
        clearServerError(this);
      });
      inputs[i].addEventListener('change', function () {
        clearServerError(this);
      });
    }
  }

  function clearServerError(input) {
    var parent = input.parentNode;
    if (!parent) return;
    var feedbacks = parent.querySelectorAll('.invalid-feedback.d-block');
    for (var j = 0; j < feedbacks.length; j++) {
      feedbacks[j].classList.remove('d-block');
      feedbacks[j].style.display = 'none';
      feedbacks[j].textContent = '';
    }
    input.classList.remove('is-invalid');
  }

  function initServerErrors() {
    var input = qs('id_email');
    if (!input) return;
    var parent = input.parentNode;
    if (!parent) return;
    var feedbacks = parent.querySelectorAll('.invalid-feedback.d-block');
    for (var i = 0; i < feedbacks.length; i++) {
      if (feedbacks[i].textContent.trim()) {
        input.classList.add('is-invalid');
        break;
      }
    }
  }

  function qs(id) {
    return document.getElementById(id);
  }

  function setFeedback(inputId, feedbackId, valido, mensagem) {
    var input = qs(inputId);
    var feedback = qs(feedbackId);
    if (!input || !feedback) return;
    input.classList.remove('is-invalid', 'is-valid');
    feedback.textContent = '';
    if (valido === true) {
      input.classList.add('is-valid');
    } else if (valido === false) {
      input.classList.add('is-invalid');
      feedback.textContent = mensagem || '';
    }
  }

  // ─── Password match ─────────────────────────────────────────

  function initPasswordMatch() {
    var senha = qs('id_senha');
    var confirmacao = qs('id_senha_confirmacao');
    if (!senha || !confirmacao) return;

    function check() {
      var sv = senha.value;
      var cv = confirmacao.value;
      if (!cv) {
        setFeedback('id_senha_confirmacao', 'senha-confirmacao-feedback', null);
        return;
      }
      if (cv === sv) {
        setFeedback('id_senha_confirmacao', 'senha-confirmacao-feedback', true);
      } else {
        setFeedback('id_senha_confirmacao', 'senha-confirmacao-feedback', false, 'As senhas não conferem.');
      }
    }

    senha.addEventListener('input', check);
    confirmacao.addEventListener('input', check);
  }

  // ─── Email availability check ───────────────────────────────

  function initEmailCheck() {
    var emailInput = qs('id_email');
    if (!emailInput) return;

    emailInput.addEventListener('input', function () {
      var val = this.value.trim();
      clearTimeout(emailCheckTimer);

      if (!val || !EMAIL_RE.test(val)) {
        setFeedback('id_email', 'email-feedback', null);
        emailCheckLastValue = '';
        return;
      }

      emailCheckTimer = setTimeout(function () {
        if (val === emailCheckLastValue) return;
        emailCheckLastValue = val;

        setFeedback('id_email', 'email-feedback', null);

        fetch(VERIFY_URL + '?email=' + encodeURIComponent(val), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.disponivel) {
              setFeedback('id_email', 'email-feedback', true);
            } else {
              setFeedback('id_email', 'email-feedback', false, data.mensagem || 'Este e-mail já está em uso.');
            }
          })
          .catch(function () {
            // silencia falha de rede — a validação server-side pega
          });
      }, 400);
    });
  }

  // ─── Form submit validation ─────────────────────────────────

  function validateAll() {
    var valido = true;

    var senha = qs('id_senha');
    var confirmacao = qs('id_senha_confirmacao');
    if (senha && confirmacao && confirmacao.value && senha.value !== confirmacao.value) {
      setFeedback('id_senha_confirmacao', 'senha-confirmacao-feedback', false, 'As senhas não conferem.');
      valido = false;
    }

    var email = qs('id_email');
    if (email && email.value.trim() && !EMAIL_RE.test(email.value.trim())) {
      setFeedback('id_email', 'email-feedback', false, 'E-mail inválido.');
      valido = false;
    }

    return valido;
  }

  function initFormSubmit() {
    var form = document.querySelector('form');
    if (!form) return;

    form.addEventListener('submit', function (e) {
      if (!validateAll()) {
        e.preventDefault();
        if (typeof mostrarToast === 'function') {
          mostrarToast('Corrija os campos em vermelho antes de continuar.', 'error');
        }
      }
    });
  }

  return { init: init };
})();
