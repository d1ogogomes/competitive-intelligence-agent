# Cron — briefing semanal automático

O `weekly.sh` é o entry point pensado para correr semanalmente sem intervenção. Faz fetch, diff, e pede ao agente para gerar o relatório.

## Recomendado: domingo à noite

Briefing pronto na segunda de manhã, com o último ciclo de releases das empresas (a maioria publica entre segunda e quinta).

## Instalar (macOS / Linux)

```sh
crontab -e
```

Adiciona a linha:

```cron
0 22 * * 0  /Users/diogogomes/Documents/GitHub/2026-ei-aoopii-c26/openclaw/workspace/scripts/weekly.sh >> /Users/diogogomes/Documents/GitHub/2026-ei-aoopii-c26/openclaw/state/logs/weekly.log 2>&1
```

Tradução: domingo às 22:00 (hora local), corre o `weekly.sh`, anexa stdout/stderr ao `weekly.log`. Usa caminho absoluto porque o cron tem `PATH` minimalista.

Adapta o caminho para a máquina onde for instalado (no Linux do Micael o root muda).

## Verificar

```sh
crontab -l                                 # confirmar que ficou registado
tail -f openclaw/state/logs/weekly.log     # ver execução
```

## Email

O envio por AgentMail usa `scripts/send-briefing.sh`. O ficheiro Markdown em
`reports/` continua a ser a fonte de verdade, mas o email é enviado com corpo
HTML e fallback em texto. Não enviar Markdown cru: fica pouco legível em vários
clientes de email.

Nota de preferência: a versão Markdown do relatório está perfeita como artefacto
principal. Não simplificar nem substituir o Markdown; apenas renderizar essa
mesma versão em HTML quando for enviada por email.

O HTML de email deve ficar limpo e apresentável. Quando possível, renderizar
pequenos logos/favicons nos títulos das empresas, mantendo sempre o texto do
título para clientes que bloqueiam imagens remotas.

Na primeira execução completa, o briefing deve ser tratado como baseline. Sem
snapshot anterior, não há mudanças verificadas por diff; o relatório pode
descrever sinais atuais, mas tem de dizer isso claramente.

## Pré-requisitos no host onde corre o cron

- `node` + `openclaw` global (a maioria dos cron daemons não carregam `nvm`; pode ser preciso usar caminhos absolutos do Node, ex.: `PATH=/Users/diogogomes/.nvm/versions/node/v22.20.0/bin:$PATH` no início da entrada do crontab).
- `agent-browser` instalado (`npm i -g agent-browser && agent-browser install`).
- `.env` em `openclaw/.env` com `OPENROUTER_API_KEY=...`.
- Para email: `AGENTMAIL_API_KEY`, `AGENTMAIL_INBOX_ID` e `BRIEFING_RECIPIENTS`.

## Variante para VPS

Quando o agente passar para um VPS (Oracle Free Tier ou outro), trocar para systemd timer em vez de cron — mais robusto a reboots e mais fácil de inspecionar com `journalctl`.

Esqueleto do unit (referência):

```ini
# /etc/systemd/system/intelagent-weekly.service
[Service]
Type=oneshot
User=intelagent
WorkingDirectory=/opt/intelagent/openclaw
ExecStart=/opt/intelagent/openclaw/workspace/scripts/weekly.sh
EnvironmentFile=/opt/intelagent/openclaw/.env
```

```ini
# /etc/systemd/system/intelagent-weekly.timer
[Timer]
OnCalendar=Sun 22:00
Persistent=true
[Install]
WantedBy=timers.target
```

`systemctl enable --now intelagent-weekly.timer` para activar.
