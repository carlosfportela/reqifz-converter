#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_converter.py
==================
Gera um ReqIFZ de amostra simulando problemas comuns do DNG 6.0.4
e valida se o conversor os corrige corretamente.
"""

import io
import os
import sys
import zipfile
import base64
import unittest
from pathlib import Path

# Adiciona o diretório atual ao path para importar o converter
sys.path.insert(0, str(Path(__file__).parent))

from lxml import etree
from reqifz_converter import XHTMLFixer, ReqIFZConverter, XHTML_NS_URL

# ---------------------------------------------------------------------------
# ReqIF de amostra com todos os problemas conhecidos
# ---------------------------------------------------------------------------

SAMPLE_REQIF = b"""<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
        xmlns:reqif-xhtml="http://www.w3.org/1999/xhtml"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <THE-HEADER>
    <REQ-IF-HEADER IDENTIFIER="_header" CREATION-TIME="2024-01-01T00:00:00" REQ-IF-TOOL-ID="IBM Doors Next 6.0.4" REQ-IF-VERSION="1.0" SOURCE-TOOL-ID="IBM Doors Next 6.0.4" TITLE="Teste de conversao">
    </REQ-IF-HEADER>
  </THE-HEADER>
  <CORE-CONTENT>
    <REQ-IF-CONTENT>
      <DATATYPES/>
      <SPEC-TYPES/>
      <SPEC-OBJECTS>

        <!-- Requisito 1: table dentro de p (principal incompatibilidade) -->
        <SPEC-OBJECT IDENTIFIER="_req1" LAST-CHANGE="2024-01-01T00:00:00">
          <VALUES>
            <ATTRIBUTE-VALUE-XHTML>
              <DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>_ad1</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
              <THE-VALUE>
                <reqif-xhtml:div xmlns:reqif-xhtml="http://www.w3.org/1999/xhtml">
                  <reqif-xhtml:p class="MsoNormal" lang="pt-BR">Texto antes da tabela</reqif-xhtml:p>
                  <reqif-xhtml:p>
                    <reqif-xhtml:table border="1" cellpadding="5" cellspacing="0" bgcolor="#ffffff" align="center">
                      <reqif-xhtml:tr>
                        <reqif-xhtml:th bgcolor="#cccccc" width="200" align="left">Coluna 1</reqif-xhtml:th>
                        <reqif-xhtml:th bgcolor="#cccccc" width="200">Coluna 2</reqif-xhtml:th>
                      </reqif-xhtml:tr>
                      <reqif-xhtml:tr>
                        <reqif-xhtml:td valign="top" nowrap="nowrap">Valor A</reqif-xhtml:td>
                        <reqif-xhtml:td>Valor B</reqif-xhtml:td>
                      </reqif-xhtml:tr>
                    </reqif-xhtml:table>
                  </reqif-xhtml:p>
                  <reqif-xhtml:p class="MsoNormal">Texto depois da tabela</reqif-xhtml:p>
                </reqif-xhtml:div>
              </THE-VALUE>
            </ATTRIBUTE-VALUE-XHTML>
          </VALUES>
        </SPEC-OBJECT>

        <!-- Requisito 2: img com src de arquivo no ZIP -->
        <SPEC-OBJECT IDENTIFIER="_req2" LAST-CHANGE="2024-01-01T00:00:00">
          <VALUES>
            <ATTRIBUTE-VALUE-XHTML>
              <DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>_ad1</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
              <THE-VALUE>
                <reqif-xhtml:div>
                  <reqif-xhtml:p>Veja a imagem abaixo:</reqif-xhtml:p>
                  <reqif-xhtml:p>
                    <reqif-xhtml:img src="images/diagrama.png" alt="Diagrama do sistema" width="400" height="300" border="0" hspace="10" vspace="5"/>
                  </reqif-xhtml:p>
                </reqif-xhtml:div>
              </THE-VALUE>
            </ATTRIBUTE-VALUE-XHTML>
          </VALUES>
        </SPEC-OBJECT>

        <!-- Requisito 3: img com src base64 -->
        <SPEC-OBJECT IDENTIFIER="_req3" LAST-CHANGE="2024-01-01T00:00:00">
          <VALUES>
            <ATTRIBUTE-VALUE-XHTML>
              <DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>_ad1</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
              <THE-VALUE>
                <reqif-xhtml:div>
                  <reqif-xhtml:p>Imagem embutida em base64:</reqif-xhtml:p>
                  <reqif-xhtml:img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" alt="pixel" width="1" height="1"/>
                </reqif-xhtml:div>
              </THE-VALUE>
            </ATTRIBUTE-VALUE-XHTML>
          </VALUES>
        </SPEC-OBJECT>

        <!-- Requisito 4: font, estilo MS Word, atributos proibidos -->
        <SPEC-OBJECT IDENTIFIER="_req4" LAST-CHANGE="2024-01-01T00:00:00">
          <VALUES>
            <ATTRIBUTE-VALUE-XHTML>
              <DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>_ad1</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
              <THE-VALUE>
                <reqif-xhtml:div>
                  <reqif-xhtml:p style="mso-line-height-rule:exactly;mso-margin-top-alt:auto;color:#333333">
                    <reqif-xhtml:font color="red" face="Arial" size="3">Texto em fonte colorida</reqif-xhtml:font>
                    <reqif-xhtml:span class="highlight" style="mso-highlight:yellow;background-color:yellow">Destaque</reqif-xhtml:span>
                  </reqif-xhtml:p>
                  <reqif-xhtml:ul compact="compact">
                    <reqif-xhtml:li>Item 1</reqif-xhtml:li>
                    <reqif-xhtml:li>Item 2</reqif-xhtml:li>
                  </reqif-xhtml:ul>
                </reqif-xhtml:div>
              </THE-VALUE>
            </ATTRIBUTE-VALUE-XHTML>
          </VALUES>
        </SPEC-OBJECT>

        <!-- Requisito 5: p com ul/ol (blocos dentro de inline) -->
        <SPEC-OBJECT IDENTIFIER="_req5" LAST-CHANGE="2024-01-01T00:00:00">
          <VALUES>
            <ATTRIBUTE-VALUE-XHTML>
              <DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>_ad1</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
              <THE-VALUE>
                <reqif-xhtml:div>
                  <reqif-xhtml:p>
                    <reqif-xhtml:ul>
                      <reqif-xhtml:li>Requisito funcional A</reqif-xhtml:li>
                      <reqif-xhtml:li>Requisito funcional B</reqif-xhtml:li>
                    </reqif-xhtml:ul>
                  </reqif-xhtml:p>
                </reqif-xhtml:div>
              </THE-VALUE>
            </ATTRIBUTE-VALUE-XHTML>
          </VALUES>
        </SPEC-OBJECT>

      </SPEC-OBJECTS>
      <SPECIFICATIONS/>
    </REQ-IF-CONTENT>
  </CORE-CONTENT>
</REQ-IF>
"""

# Imagem fake para simular arquivo existente no ZIP
FAKE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def create_sample_reqifz(path: str):
    """Cria um arquivo .reqifz de amostra com problemas de compatibilidade."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("sample.reqif", SAMPLE_REQIF)
        zf.writestr("images/diagrama.png", FAKE_PNG)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestXHTMLFixer(unittest.TestCase):

    def _make_fixer(self):
        return XHTMLFixer(
            extracted_images={},
            zip_filenames={"images/diagrama.png"},
        )

    def _parse_xhtml(self, xml_str: str):
        """Faz parse de um fragmento XHTML e retorna o elemento raiz."""
        full = f'<root xmlns:reqif-xhtml="{XHTML_NS_URL}">{xml_str}</root>'
        return etree.fromstring(full.encode("utf-8"))

    # ------------------------------------------------------------------
    # Teste 1: table dentro de p
    # ------------------------------------------------------------------
    def test_table_inside_p_is_unwrapped(self):
        root = self._parse_xhtml("""
          <reqif-xhtml:p>
            <reqif-xhtml:table>
              <reqif-xhtml:tr><reqif-xhtml:td>Cell</reqif-xhtml:td></reqif-xhtml:tr>
            </reqif-xhtml:table>
          </reqif-xhtml:p>
        """)
        fixer = self._make_fixer()
        fixer.fix_xhtml_value(root)
        fixer.fix_p_blocks_in_tree(root)

        # Não deve haver <p> como pai de <table>
        for p in root.iter(f"{{{XHTML_NS_URL}}}p"):
            children = list(p)
            block_children = [c for c in children
                              if c.tag.split("}")[-1] in ("table", "ul", "ol", "div")]
            self.assertEqual(block_children, [],
                             "<p> ainda contém elementos de bloco após conversão")

    # ------------------------------------------------------------------
    # Teste 2: img → object
    # ------------------------------------------------------------------
    def test_img_converted_to_object(self):
        root = self._parse_xhtml(
            '<reqif-xhtml:img src="images/diagrama.png" alt="Diagrama" width="400" height="300" border="0"/>'
        )
        fixer = self._make_fixer()
        fixer.fix_xhtml_value(root)

        objects = root.findall(f"{{{XHTML_NS_URL}}}object")
        self.assertEqual(len(objects), 1, "Deve existir exatamente um <object>")
        obj = objects[0]
        self.assertEqual(obj.get("data"), "images/diagrama.png")
        self.assertIn(obj.get("type"), ("image/png", "image/jpeg", "image/gif"))
        self.assertEqual(obj.get("width"), "400")
        self.assertEqual(obj.get("height"), "300")
        # border não deve existir
        self.assertIsNone(obj.get("border"))

    # ------------------------------------------------------------------
    # Teste 3: img base64 → objeto extraído
    # ------------------------------------------------------------------
    def test_base64_img_extracted(self):
        b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        root = self._parse_xhtml(
            f'<reqif-xhtml:img src="data:image/png;base64,{b64}" alt="pixel"/>'
        )
        extracted = {}
        fixer = XHTMLFixer(extracted_images=extracted, zip_filenames=set())
        fixer.fix_xhtml_value(root)

        self.assertTrue(len(extracted) > 0, "Imagem base64 deve ser extraída")
        filename = list(extracted.keys())[0]
        self.assertTrue(filename.endswith(".png"))
        objects = root.findall(f"{{{XHTML_NS_URL}}}object")
        self.assertEqual(objects[0].get("data"), filename)

    # ------------------------------------------------------------------
    # Teste 4: atributos proibidos removidos
    # ------------------------------------------------------------------
    def test_forbidden_attributes_removed(self):
        root = self._parse_xhtml(
            '<reqif-xhtml:p class="MsoNormal" lang="pt-BR" dir="ltr">Texto</reqif-xhtml:p>'
        )
        fixer = self._make_fixer()
        fixer.fix_xhtml_value(root)
        p = root.find(f"{{{XHTML_NS_URL}}}p")
        self.assertIsNone(p.get("class"), "'class' deve ser removido")
        self.assertIsNone(p.get("lang"), "'lang' deve ser removido")
        self.assertIsNone(p.get("dir"), "'dir' deve ser removido")

    # ------------------------------------------------------------------
    # Teste 5: atributos de tabela convertidos para style
    # ------------------------------------------------------------------
    def test_table_attrs_converted_to_style(self):
        root = self._parse_xhtml(
            '<reqif-xhtml:table border="1" cellpadding="5" bgcolor="#fff" align="center" width="100%"/>'
        )
        fixer = self._make_fixer()
        fixer.fix_xhtml_value(root)
        table = root.find(f"{{{XHTML_NS_URL}}}table")
        style = table.get("style", "")
        self.assertIn("border", style)
        self.assertIn("background-color", style)
        self.assertIn("text-align", style)
        # Atributos antigos devem ter sumido
        self.assertIsNone(table.get("border"))
        self.assertIsNone(table.get("bgcolor"))
        self.assertIsNone(table.get("align"))

    # ------------------------------------------------------------------
    # Teste 6: font → span
    # ------------------------------------------------------------------
    def test_font_converted_to_span(self):
        root = self._parse_xhtml(
            '<reqif-xhtml:font color="red" face="Arial" size="3">Texto</reqif-xhtml:font>'
        )
        fixer = self._make_fixer()
        fixer.fix_xhtml_value(root)
        spans = root.findall(f"{{{XHTML_NS_URL}}}span")
        self.assertTrue(len(spans) > 0, "Deve ter convertido <font> em <span>")
        style = spans[0].get("style", "")
        self.assertIn("color:red", style)
        self.assertIn("font-family:Arial", style)

    # ------------------------------------------------------------------
    # Teste 7: estilo MS Word limpo
    # ------------------------------------------------------------------
    def test_mso_style_cleaned(self):
        root = self._parse_xhtml(
            '<reqif-xhtml:p style="mso-margin-top:0;color:#333;mso-highlight:yellow">Texto</reqif-xhtml:p>'
        )
        fixer = self._make_fixer()
        fixer.fix_xhtml_value(root)
        p = root.find(f"{{{XHTML_NS_URL}}}p")
        style = p.get("style", "")
        self.assertNotIn("mso-", style, "Propriedades mso- devem ser removidas")
        self.assertIn("color:#333", style, "Propriedades CSS padrão devem ser mantidas")

    # ------------------------------------------------------------------
    # Teste 8: ul dentro de p
    # ------------------------------------------------------------------
    def test_ul_inside_p_is_unwrapped(self):
        root = self._parse_xhtml("""
          <reqif-xhtml:div>
            <reqif-xhtml:p>
              <reqif-xhtml:ul>
                <reqif-xhtml:li>Item</reqif-xhtml:li>
              </reqif-xhtml:ul>
            </reqif-xhtml:p>
          </reqif-xhtml:div>
        """)
        fixer = self._make_fixer()
        div = root.find(f"{{{XHTML_NS_URL}}}div")
        fixer.fix_xhtml_value(div)
        fixer.fix_p_blocks_in_tree(div)

        for p in div.iter(f"{{{XHTML_NS_URL}}}p"):
            for child in p:
                tag = child.tag.split("}")[-1]
                self.assertNotIn(tag, ("ul", "ol", "table", "div"),
                                 f"<{tag}> não deve estar dentro de <p>")


class TestReqIFZConverter(unittest.TestCase):

    def setUp(self):
        self.input_path  = "test_input.reqifz"
        self.output_path = "test_output.reqifz"
        create_sample_reqifz(self.input_path)

    def tearDown(self):
        for f in [self.input_path, self.output_path]:
            if os.path.exists(f):
                os.remove(f)

    def test_full_conversion(self):
        """Testa a conversão completa do arquivo."""
        converter = ReqIFZConverter(self.input_path, self.output_path)
        converter.convert()
        self.assertTrue(os.path.exists(self.output_path))

    def test_output_is_valid_zip(self):
        """Garante que o output é um ZIP válido."""
        converter = ReqIFZConverter(self.input_path, self.output_path)
        converter.convert()
        self.assertTrue(zipfile.is_zipfile(self.output_path))

    def test_output_contains_reqif(self):
        """Garante que o ZIP de saída contém o .reqif."""
        converter = ReqIFZConverter(self.input_path, self.output_path)
        converter.convert()
        with zipfile.ZipFile(self.output_path, "r") as zf:
            names = zf.namelist()
            reqif_files = [n for n in names if n.endswith(".reqif")]
            self.assertTrue(len(reqif_files) > 0)

    def test_output_reqif_is_valid_xml(self):
        """Garante que o .reqif gerado é XML válido."""
        converter = ReqIFZConverter(self.input_path, self.output_path)
        converter.convert()
        with zipfile.ZipFile(self.output_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".reqif"):
                    data = zf.read(name)
                    try:
                        etree.parse(io.BytesIO(data))
                    except etree.XMLSyntaxError as e:
                        self.fail(f"XML inválido no arquivo {name}: {e}")

    def test_no_p_wrapping_table(self):
        """Garante que não há <p> envolvendo <table> no output."""
        converter = ReqIFZConverter(self.input_path, self.output_path)
        converter.convert()
        with zipfile.ZipFile(self.output_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".reqif"):
                    data = zf.read(name)
                    tree = etree.parse(io.BytesIO(data))
                    root = tree.getroot()
                    ns = XHTML_NS_URL
                    for p in root.iter(f"{{{ns}}}p"):
                        for child in p:
                            tag = child.tag.split("}")[-1]
                            self.assertNotIn(
                                tag, ("table", "ul", "ol", "div"),
                                f"Encontrado <{tag}> dentro de <p> no output"
                            )

    def test_base64_image_extracted_to_zip(self):
        """Garante que imagens base64 foram extraídas para o ZIP."""
        converter = ReqIFZConverter(self.input_path, self.output_path)
        converter.convert()
        with zipfile.ZipFile(self.output_path, "r") as zf:
            names = zf.namelist()
            extracted = [n for n in names if "extracted_image" in n]
            self.assertTrue(len(extracted) > 0,
                            "Imagens base64 devem ser extraídas para o ZIP")

    def test_img_converted_to_object_in_output(self):
        """Garante que não há <img> no output (todos convertidos para <object>)."""
        converter = ReqIFZConverter(self.input_path, self.output_path)
        converter.convert()
        with zipfile.ZipFile(self.output_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".reqif"):
                    data = zf.read(name)
                    tree = etree.parse(io.BytesIO(data))
                    root = tree.getroot()
                    imgs = root.findall(f".//{{{XHTML_NS_URL}}}img")
                    self.assertEqual(imgs, [],
                                     "Não deve haver <img> no output; use <object>")


# ---------------------------------------------------------------------------
# Execução dos testes
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Testes do ReqIFZ Converter (DNG 6.0.4 → ELM 7.2)")
    print("=" * 60)
    unittest.main(verbosity=2)
