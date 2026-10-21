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
Não é preciso instalar nenhuma biblioteca: o projeto usa só a biblioteca padrão.

```bash
python3 projeto.py      # no Windows: python projeto.py
```

### Configurando a chave do OCR (opção 1 — leitura de imagem)

A leitura de imagens usa a API OCR.space, que exige uma chave gratuita
([obter aqui](https://ocr.space/ocrapi/freekey)). **A chave não fica no código**: defina a variável
de ambiente `OCR_SPACE_API_KEY` antes de executar o programa.

```bash
# Linux / macOS
export OCR_SPACE_API_KEY="sua_chave"

# Windows (PowerShell)
$env:OCR_SPACE_API_KEY="sua_chave"

# Windows (Prompt de Comando)
set OCR_SPACE_API_KEY=sua_chave
```

Sem a chave, o programa continua funcionando normalmente: a opção 1 avisa que o OCR está
indisponível e oferece a **digitação manual** do texto. Todas as outras funcionalidades não dependem da chave.

Para testar o OCR, use as imagens da pasta `exemplos/` (ex.: `exemplos/livro_capa.png`)
ou cole a URL de qualquer imagem pública.

## Funcionalidades

| Opção | O que faz |
|---|---|
| 1. Capturar texto | OCR real de uma imagem (arquivo local ou URL) pela API OCR.space; se falhar ou se não houver chave, permite digitar o texto |
| 2. Pesquisar no Google | Gera o link de pesquisa do texto escolhido e oferece abri-lo no navegador |
| 3. Traduzir texto | Traduz pela API MyMemory (idioma de origem detectado) e salva a tradução na captura; também mostra o link do Google Tradutor |
| 4. Saiba mais na Wikipédia | Busca um resumo do assunto na Wikipédia em português; o termo da busca pode ser confirmado ou trocado |
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
  Quando algum registro é descartado ao carregar, o programa **avisa quantos foram** e guarda o arquivo original em
  `dados/capturas.bak` antes do próximo salvamento.
- `Ctrl+C` salva os dados antes de sair.

## Integração por arquivo (exportar / importar)

A exportação/importação em JSON permite levar o histórico para outra máquina ou integrá-lo a
outras partes da solução por meio de arquivo.

**Contrato do arquivo:** uma lista JSON de capturas, em UTF-8. Cada captura tem os campos abaixo.
Apenas `id` e `texto` (mínimo de 3 caracteres) são obrigatórios na importação; os demais, se estiverem
ausentes ou inválidos, recebem valores padrão.

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | texto | Identificador único da captura (8 caracteres) |
| `texto` | texto | Texto capturado (pode ter várias linhas, separadas por `\n`) |
| `tipo` | texto | `Texto impresso`, `Lousa/Slide` ou `Manuscrito` |
| `categoria` | texto | `Livros`, `Programação`, `Estudos`, `Idiomas`, `Documentos` ou `Outros` |
| `origem` | texto | `ocr` (veio de imagem) ou `manual` (digitado) |
| `criado_em` | texto | Data/hora local em ISO 8601, ex.: `2026-10-15T11:56:10` |
| `atualizado_em` | texto ou `null` | Data/hora da última edição |
| `traducoes` | lista | Itens `{"idioma": "en", "texto": "...", "em": "2026-10-15T12:01:44"}` |

Exemplo de uma captura:

```json
{
  "id": "c3d4e5f6",
  "texto": "Please keep the door closed\nEmergency exit only",
  "tipo": "Texto impresso",
  "categoria": "Idiomas",
  "origem": "ocr",
  "criado_em": "2026-10-15T12:10:27",
  "atualizado_em": null,
  "traducoes": [
    {"idioma": "pt", "texto": "Por favor, mantenha a porta fechada\nSaída de emergência somente", "em": "2026-10-15T12:11:02"}
  ]
}
```

Para ver a importação funcionando sem precisar de internet, escolha a opção 11 e informe
`exemplos/capturas_exemplo.json` (3 capturas prontas, com os textos das imagens de exemplo).
Capturas repetidas (mesmo `id` ou mesmo texto) e itens que estão na lixeira não são importados novamente.

## APIs externas

| API | Uso | Chave |
|---|---|---|
| [OCR.space](https://ocr.space/ocrapi) | Reconhecimento de texto em imagens | Chave gratuita, definida na variável de ambiente `OCR_SPACE_API_KEY` (veja acima) |
| [MyMemory](https://mymemory.translated.net/doc/spec.php) | Tradução | Não precisa |
| [Wikipédia](https://pt.wikipedia.org/api/rest_v1/) | Resumo do assunto | Não precisa |

Todas as falhas (sem internet, conexão interrompida, timeout, erro HTTP, resposta inválida, arquivo inexistente,
entrada inválida) são tratadas com `try/except` e mostram uma mensagem clara; o programa continua funcionando.

## Testes automatizados

Os testes usam apenas a biblioteca padrão (`unittest`) e não acessam a internet: as falhas de rede são
simuladas com um servidor local.

```bash
python3 -m unittest -v      # no Windows: python -m unittest -v
```

Cobrem o modelo de dados (validação, edição, filtro, estatísticas, importação sem duplicar), a persistência
(arquivo ausente, corrompido e com registros inválidos), a conversão de falhas de conexão em `ErroAPI` e
fluxos do menu (captura sem chave do OCR, importação do exemplo e lixeira).

## Estrutura

```
projeto.py                       # programa completo
test_projeto.py                  # testes automatizados (unittest)
exemplos/
    livro_capa.png ...           # imagens para testar o OCR
    capturas_exemplo.json        # exemplo do arquivo de integração (para a opção 11)
dados/                           # capturas.json e exportações (gerados ao executar)
README.md
INTEGRANTES.TXT
```
