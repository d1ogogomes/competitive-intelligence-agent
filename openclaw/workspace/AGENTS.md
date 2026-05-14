# intelagent

Agente de competitive intelligence. Monitoriza concorrentes no espaço de AI coding assistants, deteta mudanças nas suas páginas públicas, e produz um briefing semanal.

## O que faz

- Vai buscar páginas de concorrentes (changelogs, pricing, blogs, job listings, docs)
- Guarda snapshots em `data/snapshots/{concorrente}/{fonte}/{YYYY-MM-DD}.md`
- Compara com o snapshot anterior e identifica o que mudou
- Quando há mudanças relevantes, escreve um briefing em `reports/YYYY-WW.md`

## Concorrentes

Ver `memory/competitors.md` para a lista completa com URLs.

## Regras

- Usa `web_fetch` por defeito. Só usa browser headless se a página não devolver conteúdo útil.
- Um request de cada vez por domínio. Não martelar.
- Guarda sempre o snapshot antes de analisar. Primeiro guardar, depois pensar.
- O briefing tem de dizer o que mudou, não repetir o que já se sabia.
- Se não mudou nada numa fonte, não inventa. Diz "sem alterações" e segue.
- Escreve em português. Nomes de produtos e termos técnicos ficam em inglês.
- Não usa linguagem de marketing. Frases curtas, factuais.

## Estrutura do briefing

```
# Briefing Semanal — Semana YYYY-WW

## Resumo
3-5 bullets do mais importante.

## Cursor
- O que mudou:
- Relevância:

## GitHub Copilot
...

## Sinais cruzados
Coisas que mais de um concorrente fez ao mesmo tempo.

## Fontes
URLs consultados com data.
```

## Quando correr

Por agora: manualmente, quando pedimos.
Depois: cron semanal (domingo à noite, briefing pronto segunda de manhã).
