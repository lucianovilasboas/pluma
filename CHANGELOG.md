# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [0.1.0] - 2026-07-15

### Added

- Estrutura inicial Django 5.2 + DRF com PostgreSQL
- Apps: accounts (CustomUser UUID), redacoes, avaliacoes, corretores, dashboard
- Core de domínio em `src/essay_essay/`: dataclasses, enums, evaluators LLM
- Orquestrador multi-agente com 3 corretores LLM simulados
- Sistema de consolidação unificada via QCluster
- Prompt templates ENEM (C1-C5, consolidador, templates Detalhado/Conciso/Mínimo)
- Dashboard Bootstrap 5 + Plotly com 25+ views
- API REST com DRF (redações, avaliações, notificações, consolidações)
- 400+ testes automatizados com pytest-django
- Docker Compose com PostgreSQL, web (gunicorn) e worker (qcluster)
- Integração com Telegram para notificações
- Configuração de ambiente com uv e hatchling
