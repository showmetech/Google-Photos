# Conferência entre pastas e Google Fotos

Configurações → Sincronização → menu **Conferência online**:

- **Comparar pastas com álbuns online** faz uma consulta sem enviar arquivos.
- **Abrir relatório da conferência** mostra o resultado por álbum e um CSV por arquivo.
- **Reenviar ausências comprovadas** só fica disponível para itens que já tinham um ID online conferido, recibo local inalterado e duas consultas completas, separadas por pelo menos uma hora, confirmando ausência na biblioteca acessível ao mesmo cliente e na mesma sessão de autorização. O álbum original ainda precisa estar acessível com o mesmo ID. A ação consulta novamente antes de alterar a fila.
- Itens encontrados na biblioteca, mas fora do álbum esperado, pedem associação ao álbum existente; não são reenviados.

O serviço do próprio aplicativo faz a conferência após uma rodada de sincronização, no máximo uma vez por dia quando as consultas funcionam, e com intervalo mínimo de uma hora em caso de indisponibilidade. O mesmo bloqueio de worker protege varredura, comparação e upload. Nenhuma automação do Codex é necessária. O reparo de ausências permanece uma ação explícita no menu.

Para evitar reler toda a biblioteca, a conferência lista os álbuns acessíveis e consulta pela API oficial `mediaItems.batchGet` somente IDs previamente observados que deixaram de aparecer. Usa a autorização existente do mesmo cliente; não abre outra sessão nem solicita novas permissões. Erros de acesso e respostas incompletas não são tratados como mídia excluída.

## Limites reais da API

A Google Photos Library API só permite listar conteúdo criado pelo cliente autenticado. Ela não oferece um inventário irrestrito do acervo antigo nem hashes dos originais. Portanto:

- Recibo local não significa que o item continua online hoje.
- Nome correspondente ou contagem igual não comprovam igualdade de conteúdo.
- Álbum não acessível pela API não significa álbum ausente.
- A declaração de acervo anterior permanece separada da conferência online independente.
- Os relatórios não comprovam integridade binária de todas as fotos e vídeos.

O aplicativo guarda IDs estáveis, não base URLs temporárias. Ele não troca o cliente OAuth, extrai cookies, usa endpoints privados ou cria álbuns duplicados para contornar a restrição.

## Histórico e inventário externo

Para o histórico invisível pela API, confira o álbum na interface autenticada do Google Fotos. Pode-se importar um inventário JSON com os **nomes originais por álbum**, coletados por uma conferência autorizada, por **Importar inventário do histórico…**. O aplicativo não baixa ZIPs nem considera esse JSON autorização para enviar ou marcar arquivos como enviados. Um inventário antigo ou incompleto não comprova ausência atual.

Formato de exemplo:

```json
{
  "schema": 1,
  "captured_at": "2026-11-09T10:00:00Z",
  "albums": [{
    "title": "2026-11 - Meu álbum",
    "complete": true,
    "expected_count": 2,
    "items": [
      {"filename": "IMG_0001.heic"},
      {"filename": "VID_0002.mp4"}
    ]
  }]
}
```

Use `complete: false` se a lista não incluir todo o álbum. Uma lista incompleta ou com nomes repetidos não permite concluir que um arquivo está faltando. Exportações Takeout brutas não são importadas automaticamente: metadados podem representar datas diferentes, ter nomes truncados e omitir associações; é necessário produzir o inventário por álbum acima antes de importar.

Para uma divergência real no histórico, preserve o álbum existente e adicione somente a mídia comprovadamente ausente pela interface do Google Fotos; registre o recibo depois da confirmação. Quando a identidade do arquivo é incerta, mantenha a revisão pendente em vez de reenviar o histórico.

Referências oficiais: https://developers.google.com/photos/library/guides/access-media-items e https://developers.google.com/photos/library/reference/rest/v1/mediaItems/list
