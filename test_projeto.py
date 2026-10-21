"""
Testes automatizados do projeto (unittest, apenas biblioteca padrão).

Como executar, na pasta do projeto:
    python -m unittest -v

Os testes não acessam a internet: as falhas de rede são simuladas com um servidor local.
"""

import contextlib
import io
import json
import os
import socket
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import projeto


def silenciar() -> contextlib.AbstractContextManager:
    """Captura o que o programa imprime, para não poluir a saída dos testes."""
    return contextlib.redirect_stdout(io.StringIO())


def nova_captura(texto: str, categoria: str = "Estudos", id_: str = "") -> dict:
    """Cria uma captura de teste (com id opcional fixo)."""
    captura = projeto.criar_captura(texto, "Texto impresso", categoria, "manual")
    if id_:
        captura["id"] = id_
    return captura


class TestModeloDeDados(unittest.TestCase):
    def test_criar_captura_tem_todos_os_campos(self):
        captura = projeto.criar_captura("Olá mundo", "Manuscrito", "Livros", "ocr")
        self.assertEqual(
            set(captura),
            {"id", "texto", "tipo", "categoria", "origem", "criado_em", "atualizado_em", "traducoes"},
        )
        self.assertEqual(captura["traducoes"], [])
        self.assertIsNone(captura["atualizado_em"])

    def test_captura_valida(self):
        self.assertTrue(projeto.captura_valida({"id": "x", "texto": "abc"}))
        self.assertFalse(projeto.captura_valida({"id": "x", "texto": "ab"}))   # texto curto
        self.assertFalse(projeto.captura_valida({"texto": "abcdef"}))          # sem id
        self.assertFalse(projeto.captura_valida("não é dicionário"))

    def test_completar_captura_corrige_valores_invalidos(self):
        bruto = {"id": "x1", "texto": " Texto ok ", "tipo": "inexistente", "categoria": "???",
                 "origem": "?", "traducoes": [{"idioma": "en", "texto": "ok"}, {"idioma": 1}, "lixo"]}
        captura = projeto.completar_captura(bruto)
        self.assertEqual(captura["texto"], "Texto ok")
        self.assertEqual(captura["tipo"], "Texto impresso")
        self.assertEqual(captura["categoria"], "Outros")
        self.assertEqual(captura["origem"], "manual")
        self.assertEqual(len(captura["traducoes"]), 1)

    def test_completar_captura_mantem_valores_validos(self):
        bruto = {"id": "x2", "texto": "Fotossíntese", "tipo": "Lousa/Slide", "categoria": "Estudos",
                 "origem": "ocr", "criado_em": "2026-10-15T11:56:10"}
        captura = projeto.completar_captura(bruto)
        self.assertEqual((captura["tipo"], captura["categoria"], captura["origem"]),
                         ("Lousa/Slide", "Estudos", "ocr"))
        self.assertEqual(captura["criado_em"], "2026-10-15T11:56:10")

    def test_atualizar_captura(self):
        captura = nova_captura("Texto original")
        self.assertFalse(projeto.atualizar_captura(captura, "", None, None))  # vazio = manter
        self.assertIsNone(captura["atualizado_em"])
        self.assertTrue(projeto.atualizar_captura(captura, "Texto novo", None, "Livros"))
        self.assertEqual((captura["texto"], captura["categoria"]), ("Texto novo", "Livros"))
        self.assertIsNotNone(captura["atualizado_em"])

    def test_filtrar_capturas(self):
        capturas = [nova_captura("Python é legal", "Programação"),
                    nova_captura("PYTHON na lousa", "Estudos"),
                    nova_captura("Outro assunto", "Estudos")]
        self.assertEqual(len(projeto.filtrar_capturas(capturas)), 3)
        self.assertEqual(len(projeto.filtrar_capturas(capturas, termo="python")), 2)       # sem diferenciar maiúsculas
        self.assertEqual(len(projeto.filtrar_capturas(capturas, categoria="Estudos")), 2)
        self.assertEqual(len(projeto.filtrar_capturas(capturas, "python", "Estudos")), 1)  # combinados
        self.assertEqual(projeto.filtrar_capturas(capturas, "inexistente"), [])

    def test_contar_por_campo(self):
        capturas = [nova_captura("aaa", "Livros"), nova_captura("bbb", "Livros"), nova_captura("ccc", "Estudos")]
        self.assertEqual(projeto.contar_por_campo(capturas, "categoria"), {"Livros": 2, "Estudos": 1})

    def test_contar_por_periodo(self):
        referencia = datetime(2026, 10, 21, 12, 0, 0)
        datas = ["2026-10-21T08:00:00", "2026-10-16T10:00:00", "2026-09-25T10:00:00", "2026-08-01T10:00:00"]
        capturas = []
        for i, data in enumerate(datas):
            captura = nova_captura(f"texto {i}")
            captura["criado_em"] = data
            capturas.append(captura)
        capturas.append({"texto": "sem data"})  # registro sem criado_em não pode quebrar a contagem
        self.assertEqual(
            projeto.contar_por_periodo(capturas, referencia),
            {"Hoje": 1, "Últimos 7 dias": 2, "Últimos 30 dias": 3},
        )

    def test_mesclar_capturas_ignora_duplicadas_e_lixeira(self):
        dados = {"capturas": [nova_captura("Já existe", id_="id1")],
                 "lixeira": [nova_captura("Está na lixeira", id_="id2")]}
        novas = [nova_captura("Texto inédito", id_="id3"),
                 nova_captura("Outro texto", id_="id1"),         # mesmo id
                 nova_captura("  JÁ EXISTE ", id_="id4"),        # mesmo texto
                 nova_captura("Está na lixeira", id_="id5")]     # item da lixeira não volta
        self.assertEqual(projeto.mesclar_capturas(dados, novas), 1)
        self.assertEqual([c["id"] for c in dados["capturas"]], ["id1", "id3"])

    def test_resumir_e_validar_texto(self):
        self.assertEqual(projeto.resumir_texto("a\n b   c", 45), "a b c")
        self.assertEqual(projeto.resumir_texto("x" * 50, 10), "x" * 10 + "...")
        self.assertTrue(projeto.texto_valido("abc"))
        self.assertFalse(projeto.texto_valido("  ab  "))

    def test_url_de_busca_codifica_o_texto(self):
        url = projeto.montar_url_busca_google("café & leite")
        self.assertEqual(url, "https://www.google.com/search?q=caf%C3%A9%20%26%20leite")


class TestPersistencia(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.arquivo = self.pasta / "dados" / "capturas.json"

    def test_salvar_e_carregar_mantem_os_dados(self):
        dados = projeto.dados_vazios()
        dados["capturas"].append(nova_captura("Persistido com acento: ção"))
        self.assertTrue(projeto.salvar_dados(self.arquivo, dados))
        recarregado = projeto.carregar_dados(self.arquivo)
        self.assertEqual(recarregado["capturas"][0]["texto"], "Persistido com acento: ção")
        self.assertFalse(self.arquivo.with_suffix(".tmp").exists())  # arquivo temporário não sobra

    def test_arquivo_inexistente_comeca_vazio(self):
        self.assertEqual(projeto.carregar_dados(self.arquivo), projeto.dados_vazios())

    def test_json_corrompido_vira_backup(self):
        self.arquivo.parent.mkdir(parents=True)
        self.arquivo.write_text('{"capturas": [ {"id": ', encoding="utf-8")
        with silenciar():
            dados = projeto.carregar_dados(self.arquivo)
        self.assertEqual(dados, projeto.dados_vazios())
        self.assertTrue(self.arquivo.with_suffix(".bak").exists())

    def test_registros_invalidos_geram_aviso_e_backup(self):
        original = {"capturas": [{"id": "ok1", "texto": "Registro válido"}, {"id": "x", "texto": "ab"}, {"texto": "sem id"}],
                    "lixeira": []}
        self.arquivo.parent.mkdir(parents=True)
        self.arquivo.write_text(json.dumps(original), encoding="utf-8")
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            dados = projeto.carregar_dados(self.arquivo)
        self.assertEqual(len(dados["capturas"]), 1)
        self.assertIn("2 registro(s) inválido(s)", saida.getvalue())
        backup = json.loads(self.arquivo.with_suffix(".bak").read_text(encoding="utf-8"))
        self.assertEqual(len(backup["capturas"]), 3)  # o original completo foi preservado


def servir_uma_vez(resposta: bytes) -> str:
    """Sobe um servidor local que atende uma única conexão com `resposta` (vazia = fecha sem responder)."""
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)

    def atender():
        conexao, _ = servidor.accept()
        conexao.recv(4096)
        if resposta:
            conexao.sendall(resposta)
        conexao.close()
        servidor.close()

    threading.Thread(target=atender, daemon=True).start()
    return f"http://127.0.0.1:{servidor.getsockname()[1]}/"


class TestRequisicoesEAPIs(unittest.TestCase):
    def setUp(self):
        # Garante que o servidor local não passe por proxy configurado na máquina.
        patcher = patch.dict(os.environ, {"NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_resposta_json_valida(self):
        corpo = b'{"ok": true}'
        resposta = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n" % len(corpo) + corpo
        self.assertEqual(projeto.requisitar_json(servir_uma_vez(resposta)), {"ok": True})

    def test_conexao_fechada_sem_resposta_vira_erro_api(self):
        with self.assertRaises(projeto.ErroAPI):
            projeto.requisitar_json(servir_uma_vez(b""))

    def test_resposta_cortada_no_meio_vira_erro_api(self):
        cortada = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 500\r\n\r\n{\"a\": 1"
        with self.assertRaises(projeto.ErroAPI):
            projeto.requisitar_json(servir_uma_vez(cortada))

    def test_resposta_que_nao_e_json_vira_erro_api(self):
        corpo = b"<html>nao e json</html>"
        resposta = b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(corpo) + corpo
        with self.assertRaises(projeto.ErroAPI):
            projeto.requisitar_json(servir_uma_vez(resposta))

    def test_ocr_sem_chave_levanta_erro_api(self):
        with patch.object(projeto, "OCR_SPACE_API_KEY", ""):
            with self.assertRaises(projeto.ErroAPI):
                projeto.extrair_texto_ocr("exemplos/livro_capa.png", "por")


class TestFluxosDoMenu(unittest.TestCase):
    def test_capturar_sem_chave_cai_para_digitacao_manual(self):
        dados = projeto.dados_vazios()
        # 1 = OCR (indisponível sem chave) -> texto digitado -> tipo 1 -> categoria 6
        entradas = ["1", "Texto digitado à mão", "1", "6"]
        with patch.object(projeto, "OCR_SPACE_API_KEY", ""), \
                patch("builtins.input", side_effect=entradas), silenciar():
            alterou = projeto.capturar_texto(dados)
        self.assertTrue(alterou)
        self.assertEqual(dados["capturas"][0]["origem"], "manual")
        self.assertEqual(dados["capturas"][0]["texto"], "Texto digitado à mão")

    def test_importar_arquivo_de_exemplo(self):
        exemplo = Path(__file__).resolve().parent / "exemplos" / "capturas_exemplo.json"
        if not exemplo.exists():
            self.skipTest("exemplos/capturas_exemplo.json não encontrado")
        dados = projeto.dados_vazios()
        with patch("builtins.input", side_effect=[str(exemplo)]), silenciar():
            alterou = projeto.importar_capturas(dados)
        self.assertTrue(alterou)
        self.assertEqual(len(dados["capturas"]), 3)

    def test_remover_e_restaurar_pela_lixeira(self):
        dados = projeto.dados_vazios()
        dados["capturas"].append(nova_captura("Vai para a lixeira"))
        with patch("builtins.input", side_effect=["1", "s"]), silenciar():   # escolhe item 1 e confirma
            self.assertTrue(projeto.remover_captura(dados))
        self.assertEqual((len(dados["capturas"]), len(dados["lixeira"])), (0, 1))
        with patch("builtins.input", side_effect=["1", "1"]), silenciar():   # restaurar -> item 1
            self.assertTrue(projeto.gerenciar_lixeira(dados))
        self.assertEqual((len(dados["capturas"]), len(dados["lixeira"])), (1, 0))


if __name__ == "__main__":
    unittest.main()
