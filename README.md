# Câmera Inteligente com OCR — Sprint 4 (Computational Thinking with Python)

Challenge FIAP 2026 em parceria com a **JOVI**. Programa em Python que lê textos de imagens
(como a câmera do celular faria) e transforma esse texto em ações: pesquisar, traduzir,
consultar a Wikipédia e organizar um histórico salvo em arquivo.

## Integrantes
- Artur Fabi Brandi - RM570258
- Felipe Santos Ribas - RM569121
- Orion Cavalcante França - RM573677
- Victor Lula Heineken Rodrigues - RM570782
- Luiz Gonzaga - RM572446

## Como executar

Requisitos: **Python 3.10 ou superior** (o menu usa `match-case`) e acesso à internet para as APIs.
Não é preciso instalar nenhuma biblioteca nem configurar nada: o projeto usa só a biblioteca padrão.

```bash
python3 projeto.py      # no Windows: python projeto.py
```

Para testar o OCR, use as imagens da pasta `exemplos/` (ex.: `exemplos/livro_capa.png`)
ou cole a URL de qualquer imagem pública.

## Funcionalidades

| Opção | O que faz |
|---|---|
| 1. Capturar texto | OCR real de uma imagem (arquivo local ou URL) pela API OCR.space; se falhar, permite digitar o texto |
| 2. Pesquisar no Google | Gera o link de pesquisa do texto escolhido |
| 3. Traduzir texto | Traduz pela API MyMemory (idioma de origem detectado) e salva a tradução na captura; também mostra o link do Google Tradutor |
| 4. Saiba mais na Wikipédia | Busca um resumo do assunto na Wikipédia em português |
| 5. Ver histórico | Lista as capturas com data, tipo, categoria, origem e traduções; permite buscar por palavra e filtrar por categoria |
| 6. Editar captura | Corrige texto, tipo de fonte e categoria |
| 7. Remover captura | Move uma captura para a lixeira |
| 8. Lixeira | Restaura um item ou esvazia a lixeira definitivamente |
| 9. Estatísticas | Quantidade e percentual por tipo, categoria e origem; capturas por período; traduções salvas |
| 10. Exportar capturas | Gera `dados/exportacao_capturas.json` com o histórico |
| 11. Importar capturas | Lê um arquivo JSON exportado e adiciona as capturas que ainda não existem |
| 12. Limpar histórico | Move todas as capturas para a lixeira, após confirmação |
| 0. Sair | Encerra o programa |

Após cada funcionalidade o programa volta ao menu principal.

## Persistência de dados

Os dados ficam em `dados/capturas.json` (criado automaticamente) e são salvos após cada alteração.

- A gravação é feita em um arquivo temporário e depois renomeada, para não corromper o arquivo se o programa cair no meio.
- Se o arquivo estiver corrompido, o programa guarda uma cópia em `dados/capturas.bak` e começa vazio, sem travar.
- Registros inválidos (campos faltando ou com valores desconhecidos) são corrigidos ou descartados ao carregar/importar.
- `Ctrl+C` salva os dados antes de sair.

A exportação/importação em JSON permite levar o histórico para outra máquina ou integrá-lo a
outras partes da solução por meio de arquivo.

## APIs externas

| API | Uso | Chave |
|---|---|---|
| [OCR.space](https://ocr.space/ocrapi) | Reconhecimento de texto em imagens | Chave gratuita da equipe já incluída no código. Opcionalmente, defina `OCR_SPACE_API_KEY` para usar outra chave |
| [MyMemory](https://mymemory.translated.net/doc/spec.php) | Tradução | Não precisa |
| [Wikipédia](https://pt.wikipedia.org/api/rest_v1/) | Resumo do assunto | Não precisa |

Todas as falhas (sem internet, timeout, erro HTTP, resposta inválida, arquivo inexistente, entrada
inválida) são tratadas com `try/except` e mostram uma mensagem clara; o programa continua funcionando.

## Estrutura

```
projeto.py          # programa completo
exemplos/           # imagens para testar o OCR
dados/              # capturas.json e exportações (gerados ao executar)
README.md
INTEGRANTES.TXT
```
