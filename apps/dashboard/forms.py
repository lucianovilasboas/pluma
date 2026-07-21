from __future__ import annotations

from django import forms

from apps.accounts.models import CustomUser


class BootstrapForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-control"
            if isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} {css}".strip()


class LoginForm(BootstrapForm):
    email = forms.EmailField(label="E-mail")
    password = forms.CharField(label="Senha", widget=forms.PasswordInput)


class RegisterForm(BootstrapForm):
    nome = forms.CharField(label="Nome", max_length=255)
    email = forms.EmailField(label="E-mail")
    senha = forms.CharField(label="Senha", min_length=8, widget=forms.PasswordInput)
    senha_confirmacao = forms.CharField(
        label="Confirmar senha", min_length=8, widget=forms.PasswordInput
    )

    def __init__(self, *args, **kwargs):
        self.tipo = kwargs.pop("tipo", "aluno")
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower().strip()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def clean(self):
        cleaned = super().clean()
        senha = cleaned.get("senha")
        confirmacao = cleaned.get("senha_confirmacao")
        if senha and confirmacao and senha != confirmacao:
            raise forms.ValidationError("As senhas não conferem.")
        return cleaned


class RedacaoForm(BootstrapForm):
    titulo = forms.CharField(label="Título (opcional)", required=False, max_length=255)
    tema_ref_id = forms.UUIDField(required=False, widget=forms.HiddenInput)
    texto = forms.CharField(label="Texto", min_length=20, widget=forms.Textarea(attrs={"rows": 18}))


class AvaliacaoHumanaForm(BootstrapForm):
    redacao_id = forms.UUIDField(widget=forms.HiddenInput)
    avaliacao_id = forms.UUIDField(widget=forms.HiddenInput, required=False)
    nome_avaliador = forms.CharField(label="Avaliador", initial="humano", max_length=255)

    _NOTA_WIDGET = forms.NumberInput(attrs={"step": 40})

    c1_nota = forms.IntegerField(min_value=0, max_value=200, label="Competência 1", widget=_NOTA_WIDGET)
    c1_justificativa = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    c1_sugestoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    c2_nota = forms.IntegerField(min_value=0, max_value=200, label="Competência 2", widget=_NOTA_WIDGET)
    c2_justificativa = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    c2_sugestoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    c3_nota = forms.IntegerField(min_value=0, max_value=200, label="Competência 3", widget=_NOTA_WIDGET)
    c3_justificativa = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    c3_sugestoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    c4_nota = forms.IntegerField(min_value=0, max_value=200, label="Competência 4", widget=_NOTA_WIDGET)
    c4_justificativa = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    c4_sugestoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    c5_nota = forms.IntegerField(min_value=0, max_value=200, label="Competência 5", widget=_NOTA_WIDGET)
    c5_justificativa = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    c5_sugestoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


