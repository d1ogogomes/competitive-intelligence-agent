# Dificuldades tecnicas

## Cloud

- A maioria das clouds tem planos gratuitos curtos ou com limites agressivos.
- Oracle Cloud tem um free tier interessante, mas a disponibilidade pode falhar na criacao de instancias.
- A escolha do ZeroClaw com imagem Debian reduz friccao de debug em VPS pequenos.

## Agente

- OpenClaw foi considerado, mas a base em JavaScript pode ser pesada para free tiers mais fracos.
- ZeroClaw fica como opcao principal por ser mais leve e simples de correr via Docker Compose.
- Para este projeto, o agente deve orquestrar scripts, pesquisas web, snapshots, deteccao de mudancas e relatorios.

## Seguranca

- O gateway fica ligado a `127.0.0.1` no host por defeito.
- `data/`, `.env` e relatorios gerados ficam fora do Git para evitar segredos, auth profiles, memoria e cache.
- Num VPS, o acesso deve ser feito por tunnel, VPN ou reverse proxy com HTTPS e autenticacao.
