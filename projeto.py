# Sistema de Câmera Inteligente com OCR
# Sprint 4 - Computational Thinking with Python
# OCR real de imagens, ações contextuais (pesquisa, tradução, Wikipédia),
# persistência em JSON e integração por arquivo (exportação/importação).

import base64
import http.client
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

PASTA_PROJETO = Path(__file__).resolve().parent
ARQUIVO_DADOS = PASTA_PROJETO / "dados" / "capturas.json"
ARQUIVO_EXPORTACAO = PASTA_PROJETO / "dados" / "exportacao_capturas.json"

# A chave do OCR.space NÃO fica no código: defina a variável de ambiente OCR_SPACE_API_KEY
# (chave gratuita em https://ocr.space/ocrapi/freekey). Sem ela, o OCR fica indisponível
# e o programa oferece a digitação manual do texto.
OCR_SPACE_URL = "https://api.ocr.space/parse/image"
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "").strip()
OCR_TAMANHO_MAXIMO = 1024 * 1024  # limite do plano gratuito (1 MB)
EXTENSOES_IMAGEM = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp")

MYMEMORY_URL = "https://api.mymemory.translated.net/get"
MYMEMORY_LIMITE_CARACTERES = 500

WIKIPEDIA_API_URL = "https://pt.wikipedia.org/w/api.php"
WIKIPEDIA_RESUMO_URL = "https://pt.wikipedia.org/api/rest_v1/page/summary/"

TIMEOUT_SEGUNDOS = 20
USER_AGENT = "CameraInteligenteOCR/4.0 (projeto academico FIAP)"

# Dicionários de apoio (dados fixos do domínio da aplicação)
TIPOS_FONTE = {"1": "Texto impresso", "2": "Lousa/Slide", "3": "Manuscrito"}

CATEGORIAS = {
    "1": "Livros",
    "2": "Programação",
    "3": "Estudos",
    "4": "Idiomas",
    "5": "Documentos",
    "6": "Outros",
}

IDIOMAS = {
    "1": ("Português", "pt"),
    "2": ("Inglês", "en"),
    "3": ("Espanhol", "es"),
    "4": ("Francês", "fr"),
    "5": ("Alemão", "de"),
}

IDIOMAS_OCR = {"1": ("Português", "por"), "2": ("Inglês", "eng"), "3": ("Espanhol", "spa")}


class ErroAPI(Exception):
    """Erro de comunicação com um serviço externo, com mensagem amigável ao usuário."""


# ---------------------------------------------------------------------------
# Entrada de dados e validações
# ---------------------------------------------------------------------------

def ler_texto(mensagem: str, minimo: int = 1, permitir_vazio: bool = False) -> str:
    """Lê um texto do usuário; repete até ter `minimo` caracteres úteis (ou vazio, se permitido)."""
    while True:
        texto = input(mensagem).strip()
        if permitir_vazio and texto == "":
            return ""
        if len(texto) >= minimo:
            return texto
        print(f"[!] Digite pelo menos {minimo} caractere(s).")


def ler_inteiro(mensagem: str, minimo: int, maximo: int) -> int:
    """Lê um número inteiro entre `minimo` e `maximo`, tratando entradas não numéricas."""
    while True:
        entrada = input(mensagem).strip()
        try:
            numero = int(entrada)
        except ValueError:
            print(f"[!] \"{entrada}\" não é um número. Digite um valor entre {minimo} e {maximo}.")
            continue
        if minimo <= numero <= maximo:
            return numero
        print(f"[!] Fora do intervalo. Digite um valor entre {minimo} e {maximo}.")


def escolher_opcao(titulo: str, opcoes: dict, permitir_manter: bool = False) -> str | tuple | None:
    """
    Exibe as opções de um dicionário {chave: valor} e retorna o valor escolhido.

    Com `permitir_manter=True`, Enter vazio retorna None (usado na edição).
    """
    print(f"\n{titulo}")
    for chave, valor in opcoes.items():
        nome = valor[0] if isinstance(valor, tuple) else valor
        print(f"  {chave}. {nome}")

    dica = " (Enter mantém o atual)" if permitir_manter else ""
    while True:
        opcao = input(f"Selecione (1-{len(opcoes)}){dica}: ").strip()
        if permitir_manter and opcao == "":
            return None
        if opcao in opcoes:
            return opcoes[opcao]
        print(f"[!] Opção inválida. Escolha entre 1 e {len(opcoes)}.")


def confirmar(pergunta: str) -> bool:
    """Pede confirmação s/n e retorna True somente para 's'."""
    while True:
        resposta = input(f"{pergunta} (s/n): ").strip().lower()
        if resposta in ("s", "n"):
            return resposta == "s"
        print("[!] Responda apenas com 's' ou 'n'.")


def texto_valido(texto: str) -> bool:
    """Retorna True se o texto capturado tiver pelo menos 3 caracteres úteis."""
    return len(texto.strip()) >= 3


def resumir_texto(texto: str, limite: int = 45) -> str:
    """Retorna `texto` em uma linha, truncado em `limite` caracteres, com reticências se necessário."""
    texto = " ".join(texto.split())
    if len(texto) <= limite:
        return texto
    return texto[:limite] + "..."


# ---------------------------------------------------------------------------
# Modelo de dados (funções puras)
# ---------------------------------------------------------------------------

def agora_iso() -> str:
    """Retorna a data/hora local atual em ISO 8601 (sem fuso), precisão de segundos."""
    return datetime.now().isoformat(timespec="seconds")


def formatar_data(iso: str) -> str:
    """Formata uma data ISO para exibição no padrão brasileiro (dd/mm/aaaa hh:mm)."""
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def criar_captura(texto: str, tipo: str, categoria: str, origem: str) -> dict:
    """Monta e retorna o dicionário que representa uma captura de OCR."""
    return {
        "id": uuid.uuid4().hex[:8],
        "texto": texto,
        "tipo": tipo,
        "categoria": categoria,
        "origem": origem,  # "ocr" (imagem) ou "manual" (digitado)
        "criado_em": agora_iso(),
        "atualizado_em": None,
        "traducoes": [],
    }


def captura_valida(dado: object) -> bool:
    """Retorna True se `dado` for um dicionário com os campos mínimos de uma captura."""
    return (
        isinstance(dado, dict)
        and isinstance(dado.get("texto"), str)
        and texto_valido(dado["texto"])
        and isinstance(dado.get("id"), str)
    )


def completar_captura(dado: dict) -> dict:
    """
    Retorna uma cópia de `dado` só com os campos conhecidos, preenchendo os ausentes
    ou inválidos com valores padrão (protege contra arquivos editados à mão).
    """
    captura = criar_captura(dado["texto"].strip(), "Texto impresso", "Outros", "manual")
    captura["id"] = dado["id"]
    if dado.get("tipo") in TIPOS_FONTE.values():
        captura["tipo"] = dado["tipo"]
    if dado.get("categoria") in CATEGORIAS.values():
        captura["categoria"] = dado["categoria"]
    if dado.get("origem") in ("ocr", "manual"):
        captura["origem"] = dado["origem"]
    for campo in ("criado_em", "atualizado_em"):
        try:
            captura[campo] = datetime.fromisoformat(dado[campo]).isoformat(timespec="seconds")
        except (KeyError, TypeError, ValueError):
            pass
    if isinstance(dado.get("traducoes"), list):
        captura["traducoes"] = [
            t for t in dado["traducoes"]
            if isinstance(t, dict) and isinstance(t.get("idioma"), str) and isinstance(t.get("texto"), str)
        ]
    return captura


def atualizar_captura(captura: dict, texto: str, tipo: str, categoria: str) -> bool:
    """
    Aplica as alterações não vazias na captura e retorna True se algo mudou.

    Valores vazios/None significam "manter o atual".
    """
    novos = {"texto": texto, "tipo": tipo, "categoria": categoria}
    alterou = False
    for campo, valor in novos.items():
        if valor and valor != captura[campo]:
            captura[campo] = valor
            alterou = True
    if alterou:
        captura["atualizado_em"] = agora_iso()
    return alterou


def filtrar_capturas(capturas: list, termo: str = "", categoria: str = "") -> list:
    """Retorna as capturas cujo texto contém `termo` (sem diferenciar maiúsculas) e da `categoria`."""
    termo = termo.lower()
    return [
        captura
        for captura in capturas
        if termo in captura["texto"].lower()
        and (not categoria or captura["categoria"] == categoria)
    ]


def contar_por_campo(capturas: list, campo: str) -> dict:
    """Retorna um dicionário {valor_do_campo: quantidade} a partir das capturas."""
    contagem = {}
    for captura in capturas:
        valor = captura.get(campo, "—")
        contagem[valor] = contagem.get(valor, 0) + 1
    return contagem


def contar_por_periodo(capturas: list, referencia: datetime) -> dict:
    """Retorna quantas capturas foram feitas hoje, nos últimos 7 dias e nos últimos 30 dias."""
    limites = {
        "Hoje": referencia.replace(hour=0, minute=0, second=0, microsecond=0),
        "Últimos 7 dias": referencia - timedelta(days=7),
        "Últimos 30 dias": referencia - timedelta(days=30),
    }
    contagem = {periodo: 0 for periodo in limites}
    for captura in capturas:
        try:
            data = datetime.fromisoformat(captura["criado_em"])
        except (ValueError, KeyError, TypeError):
            continue
        for periodo, inicio in limites.items():
            if data >= inicio:
                contagem[periodo] += 1
    return contagem


def montar_url_busca_google(texto: str) -> str:
    """Retorna a URL de pesquisa no Google para o texto informado."""
    return f"https://www.google.com/search?q={urllib.parse.quote(texto)}"


def montar_url_traducao(texto: str, idioma_codigo: str) -> str:
    """Retorna a URL do Google Translate para o texto e idioma informados."""
    texto_encoded = urllib.parse.quote(texto)
    return f"https://translate.google.com/?sl=auto&tl={idioma_codigo}&text={texto_encoded}&op=translate"


def mesclar_capturas(dados: dict, novas: list) -> int:
    """
    Adiciona em `dados["capturas"]` as capturas novas que ainda não existem.

    Duplicatas são detectadas por id ou texto idêntico. Itens que estão na lixeira
    não são trazidos de volta. Retorna quantas foram adicionadas.
    """
    existentes = dados["capturas"] + dados["lixeira"]
    ids = {c["id"] for c in existentes}
    textos = {c["texto"].strip().lower() for c in existentes}

    adicionadas = 0
    for captura in novas:
        if captura["id"] in ids or captura["texto"].strip().lower() in textos:
            continue
        dados["capturas"].append(captura)
        ids.add(captura["id"])
        textos.add(captura["texto"].strip().lower())
        adicionadas += 1
    return adicionadas


# ---------------------------------------------------------------------------
# Persistência em arquivo JSON
# ---------------------------------------------------------------------------

def dados_vazios() -> dict:
    """Retorna a estrutura inicial de dados do sistema."""
    return {"capturas": [], "lixeira": []}


def carregar_dados(caminho: Path) -> dict:
    """
    Lê o arquivo JSON de dados e retorna {"capturas": [...], "lixeira": [...]}.

    Se o arquivo não existir, começa vazio. Se estiver corrompido, guarda uma cópia
    .bak para não perder nada e começa vazio.
    """
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            conteudo = json.load(arquivo)
    except FileNotFoundError:
        return dados_vazios()
    except (json.JSONDecodeError, UnicodeDecodeError):
        backup = caminho.with_suffix(".bak")
        print(f"[!] O arquivo {caminho.name} está corrompido. Cópia salva em {backup.name}.")
        try:
            caminho.replace(backup)
        except OSError as erro:
            print(f"[!] Não foi possível criar o backup: {erro}")
        return dados_vazios()
    except OSError as erro:
        print(f"[!] Não foi possível ler {caminho.name}: {erro}")
        return dados_vazios()

    if not isinstance(conteudo, dict):
        print(f"[!] Formato inesperado em {caminho.name}. Iniciando com dados vazios.")
        return dados_vazios()

    dados = dados_vazios()
    descartados = 0
    for lista in ("capturas", "lixeira"):
        itens = conteudo.get(lista, [])
        if not isinstance(itens, list):
            print(f"[!] \"{lista}\" em {caminho.name} não é uma lista e foi ignorado.")
            continue
        for item in itens:
            if captura_valida(item):
                dados[lista].append(completar_captura(item))
            else:
                descartados += 1

    if descartados:
        # Guarda o arquivo original antes que o próximo salvamento o sobrescreva sem os inválidos.
        backup = caminho.with_suffix(".bak")
        try:
            shutil.copy2(caminho, backup)
            print(f"[!] {descartados} registro(s) inválido(s) ignorado(s) em {caminho.name}. "
                  f"Original guardado em {backup.name}.")
        except OSError:
            print(f"[!] {descartados} registro(s) inválido(s) ignorado(s) em {caminho.name} "
                  "(não foi possível criar o backup).")
    return dados


def salvar_json(caminho: Path, conteudo: dict | list) -> bool:
    """
    Grava `conteudo` como JSON em `caminho` de forma segura (arquivo temporário + rename).

    Retorna True em caso de sucesso.
    """
    temporario = caminho.with_suffix(".tmp")
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)
        temporario.replace(caminho)
        return True
    except (OSError, TypeError) as erro:
        print(f"[!] Erro ao salvar {caminho.name}: {erro}")
        return False


def salvar_dados(caminho: Path, dados: dict) -> bool:
    """Salva o histórico e a lixeira no arquivo JSON de dados."""
    return salvar_json(caminho, dados)


# ---------------------------------------------------------------------------
# APIs externas
# ---------------------------------------------------------------------------

def requisitar_json(url: str, metodo: str = "GET", formulario: dict | None = None) -> dict | list:
    """
    Faz uma requisição HTTP e retorna a resposta JSON decodificada.

    `formulario` é enviado como x-www-form-urlencoded.
    Qualquer falha de rede, HTTP ou de formato vira ErroAPI com mensagem clara.
    """
    cabecalhos = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    dados_envio = None
    if formulario is not None:
        dados_envio = urllib.parse.urlencode(formulario).encode("utf-8")
        cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"

    requisicao = urllib.request.Request(url, data=dados_envio, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        raise ErroAPI(f"o serviço respondeu com erro HTTP {erro.code}.") from erro
    except urllib.error.URLError as erro:
        raise ErroAPI(f"sem conexão com o serviço ({erro.reason}). Verifique sua internet.") from erro
    except TimeoutError as erro:
        raise ErroAPI(f"o serviço não respondeu em {TIMEOUT_SEGUNDOS} segundos.") from erro
    except (OSError, http.client.HTTPException) as erro:
        # Conexão derrubada ou resposta cortada no meio (ex.: ConnectionResetError, IncompleteRead).
        raise ErroAPI("a conexão com o serviço foi interrompida. Tente novamente.") from erro
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise ErroAPI("o serviço retornou uma resposta em formato inesperado.") from erro


def ler_imagem_base64(caminho: Path) -> str:
    """
    Valida o arquivo de imagem e retorna seu conteúdo como data URI base64.

    Lança ValueError para extensão/tamanho inválidos e OSError se não puder ler.
    """
    if caminho.suffix.lower() not in EXTENSOES_IMAGEM:
        raise ValueError(f"extensão \"{caminho.suffix}\" não suportada. Use: {', '.join(EXTENSOES_IMAGEM)}")
    if caminho.stat().st_size > OCR_TAMANHO_MAXIMO:
        raise ValueError("a imagem tem mais de 1 MB (limite do plano gratuito do OCR.space).")
    conteudo = caminho.read_bytes()
    tipo = "jpeg" if caminho.suffix.lower() in (".jpg", ".jpeg") else caminho.suffix.lower().lstrip(".")
    return f"data:image/{tipo};base64," + base64.b64encode(conteudo).decode("ascii")


def resolver_caminho(caminho: str) -> Path:
    """
    Retorna o Path do arquivo informado. Caminhos relativos que não existem a partir da
    pasta atual são procurados na pasta do projeto (ex.: exemplos/livro_capa.png).
    """
    arquivo = Path(caminho).expanduser()
    if not arquivo.is_absolute() and not arquivo.exists() and (PASTA_PROJETO / arquivo).exists():
        return PASTA_PROJETO / arquivo
    return arquivo


def extrair_texto_ocr(origem: str, idioma: str) -> str:
    """
    Envia uma imagem (caminho local ou URL http/https) para a API OCR.space
    e retorna o texto reconhecido.
    """
    if not OCR_SPACE_API_KEY:
        raise ErroAPI("chave do OCR.space não configurada (variável de ambiente OCR_SPACE_API_KEY).")

    formulario = {"apikey": OCR_SPACE_API_KEY, "language": idioma, "scale": "true", "OCREngine": "2"}
    if origem.lower().startswith(("http://", "https://")):
        formulario["url"] = origem
    else:
        formulario["base64Image"] = ler_imagem_base64(resolver_caminho(origem))

    resposta = requisitar_json(OCR_SPACE_URL, metodo="POST", formulario=formulario)
    if not isinstance(resposta, dict):
        raise ErroAPI("resposta inesperada do OCR.space.")
    if resposta.get("IsErroredOnProcessing"):
        mensagens = resposta.get("ErrorMessage") or ["erro desconhecido"]
        if isinstance(mensagens, str):
            mensagens = [mensagens]
        raise ErroAPI("OCR.space: " + " ".join(mensagens))

    try:
        partes = [resultado["ParsedText"] for resultado in resposta["ParsedResults"]]
    except (KeyError, TypeError) as erro:
        raise ErroAPI("resposta do OCR.space sem o texto reconhecido.") from erro
    return "\n".join(parte.strip() for parte in partes if parte.strip())


def traduzir_via_api(texto: str, idioma_destino: str) -> str:
    """Traduz `texto` para `idioma_destino` usando a API MyMemory (idioma de origem detectado)."""
    parametros = urllib.parse.urlencode({"q": texto, "langpair": f"autodetect|{idioma_destino}"})
    resposta = requisitar_json(f"{MYMEMORY_URL}?{parametros}")
    try:
        status = int(resposta["responseStatus"])
        traducao = resposta["responseData"]["translatedText"]
    except (KeyError, TypeError, ValueError) as erro:
        raise ErroAPI("resposta inesperada da API de tradução.") from erro
    if status != 200:
        detalhe = resposta.get("responseDetails") or f"status {status}"
        if "DISTINCT LANGUAGES" in str(detalhe).upper():
            detalhe = "o texto já está no idioma escolhido."
        raise ErroAPI(f"tradução não realizada: {detalhe}")
    return traducao


def buscar_resumo_wikipedia(termo: str) -> dict | None:
    """
    Procura `termo` na Wikipédia em português e retorna {titulo, resumo, url},
    ou None se não houver artigo correspondente.
    """
    parametros = urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": termo, "srlimit": 1, "format": "json",
    })
    busca = requisitar_json(f"{WIKIPEDIA_API_URL}?{parametros}")
    try:
        resultados = busca["query"]["search"]
    except (KeyError, TypeError) as erro:
        raise ErroAPI("resposta inesperada da busca da Wikipédia.") from erro
    if not resultados:
        return None

    titulo = resultados[0]["title"]
    resumo = requisitar_json(WIKIPEDIA_RESUMO_URL + urllib.parse.quote(titulo.replace(" ", "_")))
    if not isinstance(resumo, dict) or not resumo.get("extract"):
        return None
    url = resumo.get("content_urls", {}).get("desktop", {}).get("page", "")
    return {"titulo": resumo.get("title", titulo), "resumo": resumo["extract"], "url": url}


# ---------------------------------------------------------------------------
# Funcionalidades do menu
# Cada uma retorna True quando altera os dados (para o main salvar o arquivo).
# ---------------------------------------------------------------------------

def capturar_texto(dados: dict) -> bool:
    """Captura um texto por OCR de imagem (API OCR.space) ou digitação manual e adiciona ao histórico."""
    print("\n--- CAPTURAR TEXTO ---")
    print("  1. Ler texto de uma imagem (OCR real)")
    print("  2. Digitar o texto manualmente")
    modo = ler_inteiro("Como deseja capturar? (1-2): ", 1, 2)

    if modo == 1 and not OCR_SPACE_API_KEY:
        print("[!] OCR indisponível: a variável de ambiente OCR_SPACE_API_KEY não está definida (veja o README).")
        print("    Você pode digitar o texto manualmente.")
        modo = 2

    texto = ""
    origem = "manual"
    if modo == 1:
        print("\nInforme o caminho de uma imagem (ex.: exemplos/livro_capa.png) ou uma URL.")
        caminho = ler_texto("Imagem: ", minimo=1).strip("\"'")
        nome_idioma, codigo_idioma = escolher_opcao("Idioma do texto na imagem:", IDIOMAS_OCR)
        print(f"\nEnviando imagem para o OCR ({nome_idioma})... aguarde.")
        try:
            texto = extrair_texto_ocr(caminho, codigo_idioma)
            origem = "ocr"
        except FileNotFoundError:
            print(f"[!] Arquivo não encontrado: {caminho}")
        except (ValueError, OSError) as erro:
            print(f"[!] Imagem inválida: {erro}")
        except ErroAPI as erro:
            print(f"[!] Falha no OCR: {erro}")

        if origem == "ocr" and not texto_valido(texto):
            print("[!] Nenhum texto legível foi encontrado na imagem.")
            texto, origem = "", "manual"
        elif origem == "ocr":
            print("\n[✓] Texto reconhecido:")
            print("    \"" + texto.replace("\n", "\n     ") + "\"")
            if not confirmar("Deseja salvar este texto?"):
                print("Captura descartada.")
                return False

        if origem == "manual":
            if not confirmar("Deseja digitar o texto manualmente?"):
                return False

    if origem == "manual":
        texto = ler_texto("Digite o texto: ", minimo=3)

    tipo = escolher_opcao("Qual o tipo de fonte?", TIPOS_FONTE)
    categoria = escolher_opcao("Em qual categoria o texto se encaixa?", CATEGORIAS)
    captura = criar_captura(texto, tipo, categoria, origem)
    dados["capturas"].append(captura)

    print("\n[✓] Captura salva com sucesso!")
    print(f"    Conteúdo  : \"{resumir_texto(texto, 60)}\"")
    print(f"    Tipo      : {tipo} | Categoria: {categoria} | Origem: {origem}")
    print(f"    Capturas  : {len(dados['capturas'])} registro(s) no histórico")
    return True


def listar_capturas(capturas: list) -> None:
    """Imprime uma lista numerada e resumida das capturas."""
    for i, captura in enumerate(capturas, 1):
        print(f"  {i}. [{captura['categoria']}] {resumir_texto(captura['texto'])}")


def selecionar_captura(capturas: list, acao: str) -> dict | None:
    """Exibe as capturas e retorna a escolhida pelo usuário (ou None se a lista estiver vazia)."""
    if not capturas:
        print("[!] Nenhum texto disponível. Use a opção 1 para capturar um texto.")
        return None

    print(f"\nTextos disponíveis para {acao}:")
    listar_capturas(capturas)
    escolha = ler_inteiro(f"\nEscolha um texto (1-{len(capturas)}): ", 1, len(capturas))
    return capturas[escolha - 1]


def oferecer_abrir_no_navegador(url: str) -> None:
    """Pergunta se o usuário quer abrir `url` no navegador padrão e abre em caso afirmativo."""
    if not confirmar("Abrir no navegador?"):
        return
    try:
        aberto = webbrowser.open(url)
    except webbrowser.Error:
        aberto = False
    if not aberto:
        print("[!] Não foi possível abrir o navegador. Copie o link acima.")


def pesquisar_no_google(dados: dict) -> bool:
    """Gera a URL de pesquisa no Google para um texto do histórico e oferece abri-la no navegador."""
    print("\n--- PESQUISAR NO GOOGLE ---")
    captura = selecionar_captura(dados["capturas"], "pesquisa")
    if captura is None:
        return False

    url = montar_url_busca_google(captura["texto"])
    print("\n[✓] Link de pesquisa gerado!")
    print(f"    Texto : \"{resumir_texto(captura['texto'], 60)}\"")
    print(f"    URL   : {url}")
    oferecer_abrir_no_navegador(url)
    return False


def traduzir_texto(dados: dict) -> bool:
    """Traduz um texto do histórico pela API MyMemory e guarda a tradução na captura."""
    print("\n--- TRADUZIR TEXTO ---")
    captura = selecionar_captura(dados["capturas"], "tradução")
    if captura is None:
        return False

    nome_idioma, codigo = escolher_opcao("Idioma de destino:", IDIOMAS)
    texto = captura["texto"]
    if len(texto) > MYMEMORY_LIMITE_CARACTERES:
        print(f"[!] Texto longo: serão traduzidos só os primeiros {MYMEMORY_LIMITE_CARACTERES} caracteres.")
        texto = texto[:MYMEMORY_LIMITE_CARACTERES]

    print("\nTraduzindo... aguarde.")
    try:
        traducao = traduzir_via_api(texto, codigo)
    except ErroAPI as erro:
        url = montar_url_traducao(captura["texto"], codigo)
        print(f"[!] Não foi possível traduzir: {erro}")
        print(f"    Use o link do Google Tradutor: {url}")
        oferecer_abrir_no_navegador(url)
        return False

    print("\n[✓] Tradução concluída!")
    print(f"    Original ({resumir_texto(captura['texto'], 60)})")
    print(f"    {nome_idioma:<9}: {traducao}")
    print(f"    Ver no Google Tradutor: {montar_url_traducao(captura['texto'], codigo)}")

    # Mantém apenas a tradução mais recente de cada idioma.
    captura["traducoes"] = [t for t in captura["traducoes"] if t.get("idioma") != codigo]
    captura["traducoes"].append({"idioma": codigo, "texto": traducao, "em": agora_iso()})
    return True


def consultar_wikipedia(dados: dict) -> bool:
    """Busca na Wikipédia um resumo sobre um texto do histórico."""
    print("\n--- SAIBA MAIS NA WIKIPÉDIA ---")
    captura = selecionar_captura(dados["capturas"], "consulta")
    if captura is None:
        return False

    sugestao = resumir_texto(captura["texto"], 100).rstrip(".")
    print(f"\nTermo sugerido: \"{sugestao}\"")
    termo = ler_texto("Termo da busca (Enter usa o sugerido): ", permitir_vazio=True) or sugestao
    print(f"\nBuscando \"{termo}\" na Wikipédia... aguarde.")
    try:
        resultado = buscar_resumo_wikipedia(termo)
    except ErroAPI as erro:
        print(f"[!] Não foi possível consultar a Wikipédia: {erro}")
        return False

    if resultado is None:
        print("Nenhum artigo encontrado para esse texto.")
        return False

    print(f"\n[✓] {resultado['titulo']}")
    print(f"    {resultado['resumo']}")
    if resultado["url"]:
        print(f"    Leia mais: {resultado['url']}")
    return False


def exibir_captura(numero: int, captura: dict) -> None:
    """Imprime todos os detalhes de uma captura."""
    print(f"  [{numero}] {formatar_data(captura['criado_em'])} | {captura['tipo']} | "
          f"{captura['categoria']} | origem: {captura['origem']}")
    texto = captura["texto"].replace("\n", "\n" + " " * 16)
    print(f"       Texto : \"{texto}\"")
    for traducao in captura["traducoes"]:
        print(f"       ({traducao['idioma']}) {traducao['texto']}")
    if captura.get("atualizado_em"):
        print(f"       Editado em {formatar_data(captura['atualizado_em'])}")
    print()


def visualizar_historico(dados: dict) -> bool:
    """Exibe o histórico completo, com busca opcional por palavra e filtro por categoria."""
    print("\n--- HISTÓRICO DE CAPTURAS ---")
    capturas = dados["capturas"]
    if not capturas:
        print("Nenhum texto capturado ainda.")
        return False

    termo = ler_texto("Buscar por palavra (Enter para todas): ", permitir_vazio=True)
    categoria = ""
    if confirmar("Filtrar por categoria?"):
        categoria = escolher_opcao("Categoria:", CATEGORIAS)

    encontradas = filtrar_capturas(capturas, termo, categoria)
    if not encontradas:
        print("\nNenhuma captura corresponde à busca.")
        return False

    print(f"\nExibindo {len(encontradas)} de {len(capturas)} registro(s):\n")
    for i, captura in enumerate(encontradas, 1):
        exibir_captura(i, captura)
    return False


def editar_captura(dados: dict) -> bool:
    """Permite corrigir o texto, o tipo de fonte e a categoria de uma captura."""
    print("\n--- EDITAR CAPTURA ---")
    captura = selecionar_captura(dados["capturas"], "edição")
    if captura is None:
        return False

    print(f"\nTexto atual: \"{captura['texto']}\"")
    novo_texto = ler_texto("Novo texto (Enter mantém o atual): ", minimo=3, permitir_vazio=True)
    novo_tipo = escolher_opcao(f"Tipo de fonte (atual: {captura['tipo']}):", TIPOS_FONTE, permitir_manter=True)
    nova_categoria = escolher_opcao(
        f"Categoria (atual: {captura['categoria']}):", CATEGORIAS, permitir_manter=True
    )

    texto_mudou = bool(novo_texto) and novo_texto != captura["texto"]
    if not atualizar_captura(captura, novo_texto, novo_tipo, nova_categoria):
        print("Nenhuma alteração realizada.")
        return False

    if texto_mudou and captura["traducoes"]:
        captura["traducoes"] = []
        print("[i] As traduções antigas foram removidas porque o texto mudou.")
    print("[✓] Captura atualizada com sucesso.")
    return True


def remover_captura(dados: dict) -> bool:
    """Move uma captura escolhida para a lixeira (pode ser restaurada depois)."""
    print("\n--- REMOVER CAPTURA ---")
    captura = selecionar_captura(dados["capturas"], "remoção")
    if captura is None:
        return False

    if not confirmar(f"Mover \"{resumir_texto(captura['texto'])}\" para a lixeira?"):
        print("Operação cancelada.")
        return False

    dados["capturas"].remove(captura)
    dados["lixeira"].append(captura)
    print("[✓] Captura movida para a lixeira. Use a opção 8 para restaurá-la.")
    return True


def gerenciar_lixeira(dados: dict) -> bool:
    """Mostra a lixeira e permite restaurar um item ou esvaziá-la definitivamente."""
    print("\n--- LIXEIRA ---")
    lixeira = dados["lixeira"]
    if not lixeira:
        print("A lixeira está vazia.")
        return False

    print(f"\n{len(lixeira)} item(ns) na lixeira:")
    listar_capturas(lixeira)
    print("\n  1. Restaurar um item")
    print("  2. Esvaziar a lixeira (definitivo)")
    print("  0. Voltar")
    opcao = ler_inteiro("Escolha (0-2): ", 0, 2)

    if opcao == 1:
        indice = ler_inteiro(f"Qual item restaurar? (1-{len(lixeira)}): ", 1, len(lixeira))
        captura = lixeira.pop(indice - 1)
        dados["capturas"].append(captura)
        print(f"[✓] \"{resumir_texto(captura['texto'])}\" restaurada para o histórico.")
        return True

    if opcao == 2:
        if not confirmar(f"Apagar definitivamente {len(lixeira)} item(ns)?"):
            print("Operação cancelada.")
            return False
        quantidade = len(lixeira)
        lixeira.clear()
        print(f"[✓] {quantidade} item(ns) apagado(s) definitivamente.")
        return True

    return False


def imprimir_contagem(titulo: str, contagem: dict, total: int) -> None:
    """Imprime uma contagem {rótulo: quantidade} com percentual sobre `total`."""
    print(f"\n  {titulo}")
    for rotulo, quantidade in sorted(contagem.items(), key=lambda item: -item[1]):
        percentual = (quantidade / total) * 100 if total else 0
        print(f"    {rotulo:<16}: {quantidade} ({percentual:.1f}%)")


def visualizar_estatisticas(dados: dict) -> bool:
    """Exibe estatísticas por tipo, categoria, origem e período, além do total de traduções."""
    print("\n--- ESTATÍSTICAS DE CAPTURAS ---")
    capturas = dados["capturas"]
    if not capturas:
        print("Nenhum texto capturado ainda. Não há estatísticas para exibir.")
        return False

    total = len(capturas)
    print(f"\nTotal de capturas: {total} | Na lixeira: {len(dados['lixeira'])}")
    imprimir_contagem("Por tipo de fonte:", contar_por_campo(capturas, "tipo"), total)
    imprimir_contagem("Por categoria:", contar_por_campo(capturas, "categoria"), total)
    imprimir_contagem("Por origem:", contar_por_campo(capturas, "origem"), total)

    print("\n  Por período:")
    for periodo, quantidade in contar_por_periodo(capturas, datetime.now()).items():
        print(f"    {periodo:<16}: {quantidade}")

    traducoes = sum(len(c["traducoes"]) for c in capturas)
    print(f"\n  Traduções salvas: {traducoes}")
    return False


def exportar_capturas(dados: dict) -> bool:
    """Exporta as capturas do histórico para um arquivo JSON que pode ser compartilhado."""
    print("\n--- EXPORTAR CAPTURAS ---")
    if not dados["capturas"]:
        print("[!] Não há capturas para exportar.")
        return False

    if salvar_json(ARQUIVO_EXPORTACAO, dados["capturas"]):
        print(f"[✓] {len(dados['capturas'])} captura(s) exportada(s) para {ARQUIVO_EXPORTACAO}")
    return False


def importar_capturas(dados: dict) -> bool:
    """Importa capturas de um arquivo JSON (lista de capturas, como o gerado pela exportação)."""
    print("\n--- IMPORTAR CAPTURAS ---")
    caminho = ler_texto(f"Arquivo para importar (Enter = {ARQUIVO_EXPORTACAO.name}): ", permitir_vazio=True)
    arquivo = resolver_caminho(caminho.strip("\"'")) if caminho else ARQUIVO_EXPORTACAO

    try:
        with open(arquivo, "r", encoding="utf-8") as origem:
            conteudo = json.load(origem)
    except FileNotFoundError:
        print(f"[!] Arquivo não encontrado: {arquivo}")
        return False
    except json.JSONDecodeError as erro:
        print(f"[!] O arquivo não é um JSON válido (linha {erro.lineno}).")
        return False
    except UnicodeDecodeError:
        print("[!] O arquivo não está em UTF-8 e não pode ser importado.")
        return False
    except OSError as erro:
        print(f"[!] Não foi possível ler o arquivo: {erro}")
        return False

    if not isinstance(conteudo, list):
        print("[!] Formato inválido: o arquivo deve conter uma lista de capturas.")
        return False

    validas = [completar_captura(item) for item in conteudo if captura_valida(item)]
    adicionadas = mesclar_capturas(dados, validas)
    ignoradas = len(conteudo) - adicionadas
    print(f"[✓] {adicionadas} captura(s) importada(s). {ignoradas} ignorada(s) "
          "(já existem no histórico ou na lixeira, ou são inválidas).")
    return adicionadas > 0


def limpar_historico(dados: dict) -> bool:
    """Move todas as capturas para a lixeira após confirmação explícita."""
    print("\n--- LIMPAR HISTÓRICO ---")
    if not dados["capturas"]:
        print("O histórico já está vazio.")
        return False

    quantidade = len(dados["capturas"])
    if not confirmar(f"Mover {quantidade} captura(s) para a lixeira?"):
        print("Operação cancelada.")
        return False

    dados["lixeira"].extend(dados["capturas"])
    dados["capturas"].clear()
    print(f"[✓] {quantidade} captura(s) movida(s) para a lixeira.")
    return True


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def exibir_menu(total_capturas: int) -> None:
    """Renderiza o menu principal com todas as opções numeradas."""
    print("\n" + "=" * 52)
    print("       CÂMERA INTELIGENTE COM OCR")
    print(f"       {total_capturas} captura(s) salva(s)")
    print("=" * 52)
    print("  1. Capturar texto (OCR de imagem ou digitação)")
    print("  2. Pesquisar texto no Google")
    print("  3. Traduzir texto")
    print("  4. Saiba mais na Wikipédia")
    print("  5. Ver histórico (com busca e filtro)")
    print("  6. Editar captura")
    print("  7. Remover captura")
    print("  8. Lixeira (restaurar / esvaziar)")
    print("  9. Estatísticas")
    print(" 10. Exportar capturas (arquivo JSON)")
    print(" 11. Importar capturas (arquivo JSON)")
    print(" 12. Limpar histórico")
    print("  0. Sair")
    print("=" * 52)


def main() -> None:
    """Loop principal: carrega os dados, roteia as opções do menu e salva após cada alteração."""
    dados = carregar_dados(ARQUIVO_DADOS)

    acoes = {
        "1": capturar_texto,
        "2": pesquisar_no_google,
        "3": traduzir_texto,
        "4": consultar_wikipedia,
        "5": visualizar_historico,
        "6": editar_captura,
        "7": remover_captura,
        "8": gerenciar_lixeira,
        "9": visualizar_estatisticas,
        "10": exportar_capturas,
        "11": importar_capturas,
        "12": limpar_historico,
    }

    print("\nBem-vindo ao Sistema de Câmera Inteligente com OCR!")
    print(f"Dados carregados de {ARQUIVO_DADOS.relative_to(PASTA_PROJETO)}.")

    try:
        while True:
            exibir_menu(len(dados["capturas"]))
            opcao = input("Escolha uma opção: ").strip()

            match opcao:
                case "0":
                    print("\nEncerrando o sistema. Até logo!")
                    break
                case _ if opcao in acoes:
                    if acoes[opcao](dados) and salvar_dados(ARQUIVO_DADOS, dados):
                        print("    (alterações salvas)")
                case _:
                    print("\n[!] Opção inválida. Escolha um número do menu.")
    except (KeyboardInterrupt, EOFError):
        print("\n\nExecução interrompida. Salvando os dados...")
        salvar_dados(ARQUIVO_DADOS, dados)
        print("Até logo!")


if __name__ == "__main__":
    main()
