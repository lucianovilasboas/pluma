---
name: run-python
description: Executa scripts Python no projeto atual. Use para localizar o arquivo, escolher o interpretador correto, rodar o script com ou sem argumentos e resumir erros de execução.
argument-hint: Informe o script Python e, se necessário, os argumentos. Exemplo: main.py ou src/app.py --modo teste.
user-invocable: true
disable-model-invocation: false
---

# Executar Python

Use este skill para executar scripts Python no workspace atual de forma objetiva e previsível.

## Quando Usar
- Rodar um arquivo Python específico.
- Executar um script com argumentos.
- Confirmar a saída de um programa.
- Diagnosticar um erro simples de execução.
- Descobrir o comando correto para rodar um arquivo no projeto.

## Procedimento
1. Identifique o arquivo Python que o usuário quer executar.
2. Confirme se o arquivo existe no workspace.
3. Configure ou identifique o interpretador Python apropriado antes da execução.
4. Monte o comando com o interpretador correto e o caminho do script.
5. Inclua argumentos somente se o usuário os tiver informado.
6. Execute o script.
7. Resuma a saída ou o erro de forma curta e direta.

## Como Escolher o Comando
- Se houver um interpretador Python já configurado no workspace, prefira esse interpretador.
- Se não houver contexto adicional, use o Python padrão disponível no ambiente.
- Para arquivo na raiz do projeto, use comando como `python main.py`.
- Para arquivo em subpastas, use o caminho relativo correto, como `python src/main.py`.
- Para argumentos, acrescente-os ao final do comando, como `python main.py --modo teste`.

## Diagnóstico Básico
- Se o arquivo não existir, informe claramente que o caminho está incorreto.
- Se houver erro de importação, destaque o módulo ausente.
- Se houver erro de sintaxe, informe que o script não pôde ser interpretado e destaque a parte mais relevante da mensagem.
- Se o script executar com sucesso, mostre a saída principal sem excesso de detalhes.

## Critérios de Conclusão
- O arquivo a ser executado foi identificado.
- O comando correto foi montado.
- O script foi executado ou o bloqueio real foi informado.
- A saída ou falha foi resumida com clareza.

## Formato da Resposta
- Comando usado.
- Resultado da execução.
- Próximo passo, apenas se necessário.


