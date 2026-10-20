# Certificado público do Supabase

`supabase-prod-ca-2021.crt` foi obtido em 20/10/2026 pelo link **Download certificate** do painel **Database > Settings > SSL configuration** do projeto. Não contém chave privada nem credenciais.

Origem HTTPS: https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt

SHA-256 do arquivo: `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`.

O libpq validou a cadeia TLS e o hostname do Session pooler usando este certificado, chegando ao pedido de senha sem fornecer credenciais. A verificação usando somente autoridades do sistema falhou. Se o provedor renovar a autoridade certificadora, confirme o novo arquivo no painel oficial e atualize o arquivo e seu hash no configurador após revisão. Não desative a validação de certificado.

Documentação: https://supabase.com/docs/guides/database/connecting-to-postgres
