# Conferência histórica e recuperação

O serviço mantém um único worker. Quando só restam arquivos bloqueados para
reconciliação web, o agendamento continua executando `scan`, evitando repetir
uploads inviáveis pela API. Após descobrir um arquivo elegível, o fluxo existente
agenda o envio. Erros transitórios continuam seguindo a política de tentativas.
Esta alteração não confirma pendências nem libera um álbum bloqueado.

`backend/compare_originals.py` compara evidências sem escrever no banco. Recebe
`--inventory` (schema 1, account, captured_at, albums com title, complete,
expected_count e items com filename, id e originalBackup), `--files` (lista JSON
de path/album), `--account` e `--output`. Opcionalmente recebe `--originals`, um
mapa JSON de ID online para caminho do original baixado individualmente pela
interface autenticada. O operador deve assegurar a proveniência desse download;
a ferramenta não autentica a origem de arquivos fornecidos pelo operador.

Presença no inventário web e igualdade binária são estados independentes.
O relatório é datado e consultivo: não representa consulta online atual, upload
recente, autorização de reparo nem exclusão. Conta diferente, ambiguidades,
inventário incompleto, originais vazios e arquivos modificados durante a leitura
não produzem confirmação binária. Hash diferente pode refletir transformação do
download; requer análise e nunca provoca reenvio automático.

A API oficial limita acesso ao conteúdo criado pelo app. Downloads de vídeo pela
API podem ser transcodificados. Não tentar corrigir isso trocando cliente OAuth,
criando álbuns duplicados, extraindo cookies ou usando endpoints privados.

Referências oficiais:
- https://developers.google.com/photos/library/guides/get-started-library
- https://developers.google.com/photos/library/guides/access-media-items

Uma origem ausente não comprova intenção de exclusão nem identidade do item
online. Mover, renomear, falhar na leitura ou ficar indisponível no Drive deve
permanecer distinto de exclusão comprovada. Nunca excluir por nome/contagem.
