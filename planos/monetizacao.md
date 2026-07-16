# Plano de Monetização — Pluma

> Documento consolidado das decisões sobre modelo de negócio, planos de
> assinatura, precificação e pagamento de corretores humanos.
> Gerado em: 09/07/2026

---

## 1. Modelo de Negócio

- **Tipo:** SaaS (assinatura mensal) + créditos avulsos
- **Processador:** Stripe (cartão de crédito)
- **Troca de plano:** imediata com prorata
- **Correção humana avulsa:** comprada separadamente como crédito extra

---

## 2. Planos de Assinatura (Alunos)

| Plano | Preço | Redações/mês | Corretores IA | Corretores Humanos |
|-------|-------|--------------|---------------|-------------------|
| Grátis | R$ 0 | 3 | 1 | ❌ |
| Básico | R$ 29 | 10 | 2 | ❌ (avulso) |
| Médio | R$ 59 | 20 | 2 | ❌ (avulso) |
| Plus | R$ 99 | Ilimitado | 3 | ❌ (avulso) |

### Correção Humana Avulsa

| Item | Preço | Custo (pago ao corretor) | Margem |
|------|-------|--------------------------|--------|
| 1 correção humana | R$ 9,90 | R$ 6,00 | R$ 3,90 (39%) |
| Pacote 5 correções | R$ 39 | R$ 30 | R$ 9,00 (23%) |
| Pacote 10 correções | R$ 69 | R$ 60 | R$ 9,00 (13%) |

### Regras de Planos

- Plano Grátis: 3 correções/mês apenas com IA (1 corretor LLM)
- Planos pagos incluem apenas corretores IA; corretor humano é sempre avulso
- Upgrade/downgrade imediato com prorata (Stripe gerencia)
- Cancelamento: volta para Grátis no fim do ciclo
- Inadimplência: sistema bloqueia novas redações, avisa por e-mail

---

## 3. Pagamento dos Corretores Humanos

### 3.1 Modelo de Remuneração

- **Valor por correção:** R$ 6,00 (600 centavos)
- **Tempo médio:** 15-20 min por redação
- **Equivalência horária:** ~R$ 18-24/h
- **Frequência de pagamento:** Mensal (fechamento no dia 1, pagamento até dia 10)

### 3.2 Dados do Corretor (campos em `CustomUser`)

- `cpf` (CharField, 11 chars)
- `chave_pix` (CharField)
- `dados_bancarios` (JSONField — banco, agência, conta)
- `status_corretor` (choices: `pendente`, `aprovado`, `suspenso`)

### 3.3 Fluxo da Correção Humana Paga

```
Aluno compra correção humana avulsa (R$ 9,90 via Stripe)
    ↓
Redação entra na fila "com correção humana"
    ↓
Corretor vê no dashboard / corrigir
    ↓
Corretor faz a correção (notas + anotações)
    ↓
Sistema cria CorrecaoPaga (R$ 6,00 = 600 centavos, status="a_pagar")
    ↓
Atualiza consolidação da redação
    ↓
Aluno vê resultado com correção humana + IA

--- Fim do mês ---

Admin gera PagamentoCorretor (lote do período)
    ↓
Processa pagamento via Pix/Stripe Connect
    ↓
Status da CorrecaoPaga vira "pago"
    ↓
Corretor recebe notificação de pagamento
```

---

## 4. Modelos de Dados Previstos

### 4.1 `apps/assinaturas/models.py`

```python
class Plano(Model):
    slug = CharField(unique)                    # 'free', 'basic', 'medium', 'plus'
    nome = CharField                             # ex: "Básico"
    descricao = TextField
    preco_centavos = IntegerField                # 0, 2900, 5900, 9900
    stripe_price_id = CharField                  # ID do Price no Stripe
    limite_redacoes_mes = IntegerField           # 0 = ilimitado
    max_corretores_humanos = IntegerField
    max_corretores_ia = IntegerField
    ativo = BooleanField(default=True)
    ordem = PositiveIntegerField(default=0)

class Assinatura(Model):
    usuario = OneToOneField(CustomUser)
    plano = ForeignKey(Plano)
    status = CharField(choices)                  # ativa, cancelada, inadimplente
    stripe_subscription_id = CharField
    ciclo_atual_inicio = DateTimeField
    ciclo_atual_fim = DateTimeField
    criada_em = DateTimeField(auto_now_add=True)
    atualizada_em = DateTimeField(auto_now=True)

class PedidoCredito(Model):
    """Compra de correção humana avulsa."""
    usuario = ForeignKey(CustomUser)
    stripe_session_id = CharField
    preco_centavos = IntegerField                # 990, 3900, 6900
    quantidade_correcoes = IntegerField
    consumidas = IntegerField(default=0)
    criada_em = DateTimeField(auto_now_add=True)

class ConsumoRedacao(Model):
    """Registro de consumo mensal de cada aluno."""
    usuario = ForeignKey(CustomUser)
    redacao = ForeignKey(Redacao)
    mes_referencia = DateField                   # primeiro dia do mês
    tipo = CharField(choices)                    # plano ou credito
    correcao_humana = BooleanField(default=False)
    criada_em = DateTimeField(auto_now_add=True)
```

### 4.2 `apps/pagamentos/models.py`

```python
class CorrecaoPaga(Model):
    """Cada correção humana gera um débito para o corretor."""
    avaliacao = OneToOneField(Avaliacao, on_delete=PROTECT)
    corretor = ForeignKey(CustomUser, on_delete=PROTECT)
    valor_centavos = IntegerField                # 600 = R$ 6,00
    status = CharField(choices)                  # a_pagar, pago, cancelado
    pago_em = DateTimeField(nullable)
    criada_em = DateTimeField(auto_now_add=True)

class PagamentoCorretor(Model):
    """Lote mensal de pagamento a um corretor."""
    corretor = ForeignKey(CustomUser, on_delete=PROTECT)
    periodo_inicio = DateField
    periodo_fim = DateField
    valor_total_centavos = IntegerField
    correcoes = ManyToManyField(CorrecaoPaga)
    status = CharField(choices)                  # pendente, processado
    comprovante = TextField(blank=True)          # ID da transação Stripe
    criado_em = DateTimeField(auto_now_add=True)
```

---

## 5. Endpoints da API REST (DRF)

### 5.1 Assinaturas (`/api/v1/assinaturas/`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `planos` | Lista planos disponíveis |
| POST | `checkout` | Cria Stripe Checkout Session → URL de pagamento |
| POST | `portal` | Redireciona pro Stripe Customer Portal |
| POST | `trocar-plano` | Troca de plano imediato com prorata |
| GET | `minha-assinatura` | Dados da assinatura do usuário atual |
| POST | `creditos/comprar` | Compra crédito de correção humana |
| GET | `creditos/saldo` | Saldo de créditos disponíveis |
| GET | `extrato` | Histórico de consumo mensal |

### 5.2 Webhooks Stripe

| Evento | Ação |
|--------|------|
| `checkout.session.completed` | Ativar assinatura ou liberar créditos |
| `customer.subscription.updated` | Refletir mudança de plano no sistema |
| `customer.subscription.deleted` | Reverter para plano Grátis no fim do ciclo |
| `invoice.paid` | Ciclo renovado com sucesso |
| `invoice.payment_failed` | Marcar como inadimplente, notificar aluno |

---

## 6. Controle de Acesso (Quotas)

### 6.1 Verificação ao enviar redação

1. Usuário autenticado → buscar `Assinatura` ativa
2. Se não tem assinatura ou está inadimplente → usar `Plano.free`
3. Calcular consumo do mês (`ConsumoRedacao`)
4. Se `consumo >= plano.limite_redacoes_mes` → bloquear com HTTP 402

### 6.2 Seleção de corretores no pool

- Consultar `plano.max_corretores_ia` e selecionar N corretores LLM do pool
- Se o aluno tem crédito humano disponível, adicionar 1 `PoolCorretor.tipo=humano`
- Senão, apenas LLM

---

## 7. Dashboard do Corrector (Frontend)

- Página `/dashboard/correcoes-pendentes` — redações aguardando correção humana
- Página `/dashboard/meus-ganhos` — extrato com valores a receber
- Página `/dashboard/dados-bancarios` — cadastro de CPF e chave Pix
- Notificação quando nova correção humana é solicitada

---

## 8. Faturamento Esperado (Estimativa)

| Cenário | Alunos | Ticket médio | Receita | Custo corretores | Margem bruta |
|---------|--------|-------------|---------|------------------|-------------|
| Lançamento | 100 | R$ 39 | R$ 3.900 | ~R$ 500 | R$ 3.400 |
| Crescendo | 500 | R$ 45 | R$ 22.500 | ~R$ 3.000 | R$ 19.500 |
| Estável | 2.000 | R$ 49 | R$ 98.000 | ~R$ 15.000 | R$ 83.000 |

> Premissa: 30% dos alunos compram correção humana avulsa, 80% estão em planos
> pagos, ticket médio ponderado entre Grátis-Básico-Médio-Plus.

---

## 9. Observações Finais

- **Stripe Connect** será necessário para pagar os corretores de forma automatizada
  (alternativa: pagamento manual via Pix com comprovante)
- **Custo de IA** é irrelevante comparado ao humano (~R$ 0,10-0,50/redação)
- **Churn** deve ser monitorado desde o início — plano Grátis serve como funil
- **MRR** (Monthly Recurring Revenue) deve ser o KPI principal
- Primeira versão pode lançar apenas IA + avulso humano sem pagamento de
  corretores (estes corrigem como voluntários/professores parceiros)
