# Fontes a Monitorizar

5 concorrentes no espaço de AI coding assistants. 
## Concorrentes

| # | Empresa / Produto | Porquê |
|---|-------------------|--------|
| 1 | **Cursor** (Anysphere) | IDE AI, cresce rápido, pricing muda com frequência |
| 2 | **GitHub Copilot** (Microsoft) | Incumbent, releases mensais, changelogs públicos |
| 3 | **Anthropic Claude / Claude Code** | Releases de modelos visíveis, API pricing público |
| 4 | **Windsurf** (Codeium) | Pivot recente, boa fonte de sinais competitivos |
| 5 | **Zed** (Zed Industries) | Editor nativo com AI integrado, desenvolvimento público no GitHub |

---

## Fontes por concorrente

### 1. Cursor

- **Release notes:** https://cursor.com/changelog
- **Docs:** https://docs.cursor.com
- **Pricing page:** https://cursor.com/pricing
- **Blog oficial:** https://cursor.com/blog
- **Job listings:** https://cursor.com/careers
- **Social media:** X.com/@cursor_ai
- **Terms / policy:** https://cursor.com/terms

### 2. GitHub Copilot

- **Release notes:** https://github.blog/changelog/label/copilot/
- **Docs:** https://docs.github.com/copilot
- **Pricing page:** https://github.com/features/copilot/plans
- **Blog oficial:** https://github.blog/ai-and-ml/
- **Job listings:** https://github.careers
- **Social media:** X.com/@GitHubCopilot
- **Terms / policy:** https://docs.github.com/copilot/responsible-use-of-github-copilot-features

### 3. Anthropic / Claude Code

- **Release notes:** https://docs.anthropic.com/en/docs/about-claude/models
- **Docs:** https://docs.anthropic.com
- **Pricing page:** https://www.anthropic.com/pricing
- **Blog oficial:** https://www.anthropic.com/news
- **Job listings:** https://www.anthropic.com/careers
- **Social media:** X.com/@AnthropicAI
- **Terms / policy:** https://www.anthropic.com/legal/aup

### 4. Windsurf (Codeium)

- **Release notes:** https://windsurf.com/changelog
- **Docs:** https://docs.windsurf.com
- **Pricing page:** https://windsurf.com/pricing
- **Blog oficial:** https://windsurf.com/blog
- **Job listings:** https://windsurf.com/careers
- **Social media:** X.com/@windsurf_ai
- **Terms / policy:** https://windsurf.com/terms-of-service

### 5. Zed

- **Release notes:** https://zed.dev/releases
- **Docs:** https://zed.dev/docs
- **Pricing page:** https://zed.dev/pricing
- **Blog oficial:** https://zed.dev/blog
- **Job listings:** https://zed.dev/jobs
- **Social media:** X.com/@zeddotdev, GitHub: https://github.com/zed-industries/zed
- **Terms / policy:** https://zed.dev/terms-of-service

---

## O que detetar (delta detection)

O agente compara snapshots e emite sinal quando:

- **Pricing:** qualquer alteração numérica, novo tier, remoção de tier
- **Release notes:** novas entradas desde último snapshot
- **Job listings:** novas vagas (especialmente senior/research/infra — indica direção estratégica)
- **Blog:** novos posts, classificados por tipo (launch, research, partnership, incident)
- **Docs:** novos endpoints de API, modelos adicionados/removidos

## Output (briefing semanal)

Ficheiro em `workspace/reports/YYYY-WW.md`:

```md
# Weekly Briefing — Week YYYY-WW

## TL;DR
- ...

## Por concorrente
### Cursor
- O que mudou:
- O que significa:
- O que vigiar:

### GitHub Copilot
...

## Sinais cruzados
Padrões em ≥ 2 concorrentes.

## Fontes consultadas
URLs + timestamps.
```
