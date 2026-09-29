# Política de segurança

## Versões suportadas

A versão suportada é a branch `main`. Correções de segurança são publicadas nessa branch; atualize a imagem Docker após a publicação.

## Reportar uma vulnerabilidade

Não publique detalhes exploráveis em uma issue pública. Use o recurso **Report a vulnerability** na aba **Security** do GitHub para enviar um aviso privado aos mantenedores. Inclua passos de reprodução, impacto, versão/commit e uma correção sugerida, se houver.

Se o recurso privado não estiver habilitado no repositório, abra uma issue sem detalhes exploráveis pedindo um canal privado. Não envie senhas, tokens ou dados de usuários.

## Escopo de segurança

Áreas especialmente sensíveis: SSRF/DNS rebinding no scraper, validação de JWT Cloudflare Access, exposição da origem sem autenticação, XSS/CSRF, limites de requisição, prompts/resultados do Ollama e migrações SQLite.

O NewsRadar não substitui o controle de acesso de rede. Mantenha a origem inacessível pela internet pública; Cloudflare Access só protege a origem quando o tráfego direto também está restringido ou quando o app valida o JWT configurado.
