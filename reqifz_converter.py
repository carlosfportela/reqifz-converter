#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reqifz_converter.py
====================
Converte arquivos ReqIFZ exportados do IBM Doors Next Generation 6.0.4
para o formato compatível com o IBM ELM (Doors Next) 7.2.

Regras aplicadas (fusão v1 + v2):
  1. Limpeza do REQ-IF-HEADER: remove filhos fora do namespace ReqIF e
     atualiza TOOL-ID para a string do ELM 7.2.
  2. Remoção de <button>: elemento proibido; texto é preservado no pai.
  3. Atributo 'name' em <a>: convertido para 'id' e removido.
  4. IDs duplicados: atributos id repetidos são removidos.
  5. DATATYPE-DEFINITION-REAL: garante MIN/MAX quando ausentes.
  6. Atributos proibidos globais: class, lang, dir, valign, nowrap,
     compact, hspace, vspace, face, size, color, name, target, rel,
     start (em <ol>), style (em <br>).
  7. Lógica de mídia avançada:
     - <img> → <reqif-xhtml:object> com MIME real via rm:CONTENT-TYPE
     - Resolução de arquivos pelo file_map (nome → caminho relativo)
     - Imagens base64 extraídas como arquivo e referenciadas
     - <img> não resolvido é removido em vez de gerar warning silencioso
  8. <font> → <span> com style equivalente.
  9. Elementos de bloco dentro de <p>: split inteligente com novos <p>
     para conteúdo inline antes/depois do bloco (lógica do v1).
 10. Atributos de apresentação em <table>/<td>/<th>: convertidos para style.
 11. Limpeza de style: remove prefixos vendor e propriedades mso-*.
 12. Remoção de xmlns redundantes em filhos.
 13. Caracteres inválidos em XML 1.0 removidos.
 14. Declarações XML duplicadas removidas.
 15. <br> sem style, self-closing.

Uso:
  python reqifz_converter.py <arquivo_entrada.reqifz> [arquivo_saida.reqifz]

Dependências:
  - Python 3.8+
  - lxml (pip install lxml)
"""

import argparse
import base64
import copy
import io
import logging
import mimetypes
import os
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

try:
    from lxml import etree
except ImportError:
    print("Erro: a biblioteca 'lxml' é necessária.\nInstale com:  pip install lxml")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------
REQIF_NS        = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
XHTML_NS_URL    = "http://www.w3.org/1999/xhtml"
IBM_RM_NS       = "http://www.ibm.com/rm"

ELM72_TOOL_ID   = "IBM Engineering Requirements Management DOORS Next (v7.2)"

# Tags de bloco que NÃO podem estar dentro de <p>
BLOCK_TAGS = {
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "ul", "ol", "li", "dl", "dt", "dd",
    "div", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "figure", "figcaption", "section", "article", "aside",
    "header", "footer", "main", "nav",
}

# Atributos globalmente proibidos (sem exceções por tag)
ATTRS_TO_REMOVE = {
    "lang", "dir",
    "face", "size",
    "color",
    "valign", "nowrap", "compact",
    "hspace", "vspace",
    "name",
    "target", "rel",
}

MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("reqifz_converter")


# ===========================================================================
# Utilitários
# ===========================================================================

def local_name(element) -> str:
    """Retorna o nome local da tag, ignorando o namespace.
    Retorna string vazia para nós especiais (comentários, PIs) cujo .tag
    é um callable do lxml e não uma str.
    """
    tag = element.tag
    if not isinstance(tag, str):
        # Comentário XML, instrução de processamento, etc.
        return ""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def strip_xml_control_chars(text: str) -> str:
    if not text:
        return text
    return re.sub(
        r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]",
        "",
        text,
    )


def guess_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def safe_filename(name: str) -> str:
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name


# ===========================================================================
# Regras do v1 — nível de documento (operam no root lxml)
# ===========================================================================

def fix_header(root):
    """
    Regra v1-1: Limpa REQ-IF-HEADER e atualiza TOOL-ID para ELM 7.2.
    """
    ns = {"reqif": REQIF_NS}
    header = root.find(".//reqif:REQ-IF-HEADER", ns)
    if header is None:
        return
    reqif_prefix = f"{{{REQIF_NS}}}"
    for child in list(header):
        # child.tag pode ser callable (comentário/PI lxml) — ignorar esses nós
        if not isinstance(child.tag, str) or not child.tag.startswith(reqif_prefix):
            header.remove(child)
    tid = header.find("reqif:TOOL-ID", ns)
    if tid is not None:
        tid.text = ELM72_TOOL_ID
    log.info("REQ-IF-HEADER atualizado (TOOL-ID → ELM 7.2).")


def fix_duplicate_reqif_identifiers(root):
    """
    Trata elementos com IDENTIFIER duplicado (viola cvc-id.2 no ELM 7.2).

    Estratégia por tipo de elemento:
    - Elementos de ESQUEMA (ATTRIBUTE-DEFINITION-*, DATATYPE-DEFINITION-*,
      SPEC-TYPE, RELATION-GROUP-TYPE, …): a duplicata é removida, pois são
      definições estruturais que o DNG 6.0.4 exporta repetidas.
    - Elementos de CONTEÚDO (SPEC-OBJECT, SPEC-RELATION, SPEC-HIERARCHY,
      RELATION-GROUP): NÃO são removidos — são os artefatos/requisitos reais.
      Em vez disso, o IDENTIFIER duplicado recebe um sufixo único para manter
      a unicidade sem perder o artefato.
    """
    # Nomes locais de elementos que representam conteúdo (artefatos reais)
    CONTENT_ELEMENTS = {
        "SPEC-OBJECT", "SPEC-RELATION", "SPEC-HIERARCHY", "RELATION-GROUP",
    }

    seen_identifiers: dict = {}   # ident → contador de ocorrências
    dup_counters: dict = {}        # ident → próximo sufixo disponível

    for elem in root.xpath("//*[@IDENTIFIER]"):
        if not isinstance(elem.tag, str):
            continue
        ident = elem.get("IDENTIFIER")
        lname = local_name(elem)

        if ident not in seen_identifiers:
            seen_identifiers[ident] = lname
            continue

        # --- IDENTIFIER duplicado ---
        if lname in CONTENT_ELEMENTS:
            # Conteúdo: torna o IDENTIFIER único com sufixo em vez de remover
            dup_counters[ident] = dup_counters.get(ident, 1) + 1
            new_ident = f"{ident}-dup{dup_counters[ident]}"
            elem.set("IDENTIFIER", new_ident)
            log.warning(
                "SPEC-OBJECT/RELATION com IDENTIFIER duplicado renomeado: "
                "%s → %s", ident, new_ident
            )
        else:
            # Esquema: remove a duplicata (comportamento original)
            parent = elem.getparent()
            if parent is not None:
                parent.remove(elem)
                log.info(
                    "Removido elemento de esquema ReqIF duplicado "
                    "(IDENTIFIER=%s, tag=%s)", ident, lname
                )


def fix_duplicate_ids_and_anchors(root):
    """
    Regra v1-2:
    - Remove elementos <button> proibidos (texto migrado para o pai).
    - Converte atributo 'name' em <a> para 'id'.
    - Remove atributos 'id' duplicados.
    """
    xhtml_ns = XHTML_NS_URL
    seen_ids: set = set()
    for elem in root.xpath(
        "//*[@id] | //xhtml:a | //xhtml:button",
        namespaces={"xhtml": xhtml_ns},
    ):
        lname = local_name(elem)

        if lname == "button":
            parent = elem.getparent()
            if parent is not None:
                if elem.text:
                    parent.text = (parent.text or "") + elem.text
                parent.remove(elem)
            continue

        if lname == "a" and elem.get("name") is not None:
            if elem.get("id") is None:
                elem.set("id", elem.get("name"))
            del elem.attrib["name"]

        current_id = elem.get("id")
        if current_id:
            if current_id in seen_ids:
                del elem.attrib["id"]
            else:
                seen_ids.add(current_id)


def fix_datatype_real(root):
    """
    Regra v1-3: Garante MIN/MAX em DATATYPE-DEFINITION-REAL.
    """
    ns = {"reqif": REQIF_NS}
    for real in root.xpath(".//reqif:DATATYPE-DEFINITION-REAL", namespaces=ns):
        if "MIN" not in real.attrib:
            real.attrib["MIN"] = "-1.0E308"
        if "MAX" not in real.attrib:
            real.attrib["MAX"] = "1.0E308"


def fix_thead_to_tbody(root):
    """
    Regra nova: Converte <thead> e <tfoot> em <tbody> no XHTML interno.

    O schema XHTML restrito usado pelo IBM ELM 7.2 não aceita <thead> nem
    <tfoot> como filhos de <table>; apenas <tbody> é permitido.
    Todos os atributos e filhos são preservados; somente o nome da tag muda.
    """
    xhtml_ns = XHTML_NS_URL
    tbody_tag = f"{{{xhtml_ns}}}tbody"
    for elem in root.xpath(
        "//xhtml:thead | //xhtml:tfoot",
        namespaces={"xhtml": xhtml_ns},
    ):
        old_tag = local_name(elem)
        elem.tag = tbody_tag
        log.info("<%s> convertido em <tbody> (ReqIF XHTML schema).", old_tag)


def fix_prohibited_attrs(root):
    """
    Regra v1-4: Remove atributos proibidos por tag específica:
    - <ol> start, <br> style, <table> align, lang/dir/valign em todos.
    (Complementa a limpeza geral do XHTMLFixer.)
    """
    xhtml_ns = XHTML_NS_URL
    for elem in root.xpath("//xhtml:*", namespaces={"xhtml": xhtml_ns}):
        if not isinstance(elem.tag, str):
            continue  # Nó especial (comentário/PI) — pular
        lname = local_name(elem)
        if lname == "ol":
            elem.attrib.pop("start", None)
        if lname == "br":
            elem.attrib.pop("style", None)
        if lname == "table":
            elem.attrib.pop("align", None)
        for attr in ("lang", "dir", "valign"):
            elem.attrib.pop(attr, None)


# ===========================================================================
# Lógica de mídia avançada (v1-5, integrada com extração base64 do v2)
# ===========================================================================

def fix_media_elements(root, file_map: dict, extracted_images: dict):
    """
    Regra v1-5 + v2:
    - Resolve <img>/<object> usando file_map (nome → caminho relativo no ZIP).
    - Consulta rm:CONTENT-TYPE para MIME real.
    - <img> → <object> com data/type.
    - <img> com src=data:... → extrai bytes e adiciona ao ZIP de saída.
    - <img> não resolvido → removido.
    - <object> já existente → atualiza data se resolvido.
    """
    xhtml_ns = XHTML_NS_URL
    rm_ns = IBM_RM_NS
    nsmap_rm = {"rm": rm_ns}
    img_counter = [0]

    for elem in root.xpath(
        "//xhtml:object | //xhtml:img",
        namespaces={"xhtml": xhtml_ns},
    ):
        lname = local_name(elem)
        is_img = lname == "img"
        attr = "src" if is_img else "data"
        val = elem.get(attr, "")

        # --- Caso base64 (apenas em <img>) ---
        if is_img and val.startswith("data:"):
            match = re.match(r"data:([^;]+);base64,(.+)", val, re.DOTALL)
            if match:
                mime_type = match.group(1).strip()
                b64_data = match.group(2).strip().replace("\n", "").replace("\r", "")
                try:
                    raw_bytes = base64.b64decode(b64_data)
                    ext = MIME_TO_EXT.get(mime_type, ".bin")
                    img_counter[0] += 1
                    fname = f"extracted_image_{img_counter[0]:04d}{ext}"
                    extracted_images[fname] = raw_bytes
                    log.info("Imagem base64 extraída: %s (%d bytes)", fname, len(raw_bytes))
                    # Substitui por <object>
                    new_obj = etree.Element(f"{{{xhtml_ns}}}object")
                    new_obj.set("data", fname)
                    new_obj.set("type", mime_type)
                    style = elem.get("style")
                    if style:
                        new_obj.set("style", style)
                    new_obj.text = fname
                    parent = elem.getparent()
                    if parent is not None:
                        parent.replace(elem, new_obj)
                except Exception as exc:
                    log.warning("Falha ao decodificar base64: %s", exc)
            continue

        if not val:
            continue

        # --- Resolve pelo file_map ---
        resource_id = val.split("?")[0].replace("\\", "/").split("/")[-1]
        resource_id_no_ext = os.path.splitext(resource_id)[0]
        target_file = file_map.get(resource_id) or file_map.get(resource_id_no_ext)

        if target_file:
            if is_img:
                # Consulta rm:CONTENT-TYPE para o MIME real
                content_type = None
                wrapped = root.xpath(
                    f".//rm:WRAPPED-RESOURCE[@IDENTIFIER='{target_file}']/rm:CONTENT-TYPE",
                    namespaces=nsmap_rm,
                )
                if wrapped:
                    content_type = wrapped[0].text
                if not content_type:
                    content_type = guess_mime(target_file)

                new_obj = etree.Element(f"{{{xhtml_ns}}}object")
                new_obj.set("data", target_file)
                new_obj.set("type", content_type)
                style = elem.get("style")
                if style:
                    new_obj.set("style", style)
                new_obj.text = target_file
                parent = elem.getparent()
                if parent is not None:
                    parent.replace(elem, new_obj)
            else:
                elem.set("data", target_file)
        else:
            if is_img:
                # <img> não resolvido → remove para não quebrar o esquema
                log.warning("Imagem não resolvida removida: %s", val)
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem)
            # <object> não resolvido → deixar sem modificação alguma.
            # Artefatos aninhados do IBM DOORS são <object> com data=URI interna
            # que nunca aparece no file_map; modificá-los quebra a referência.
            # Comportamento idêntico ao da v1.


# ===========================================================================
# XHTMLFixer — limpeza por elemento (preserva lógica v2 + complementa v1)
# ===========================================================================

class XHTMLFixer:
    """
    Corrige o conteúdo XHTML interno dos valores XHTML do ReqIF.
    Lógica de split de <p> com blocos vem do v1 (mais precisa).
    """

    def __init__(self, zip_filenames: set):
        self.zip_filenames = zip_filenames

    def fix_xhtml_value(self, xhtml_value_elem):
        for child in list(xhtml_value_elem):
            self._process_element(child)
        # Depois da recursão, aplica split de <p> com blocos (lógica v1)
        self._fix_block_in_p(xhtml_value_elem)

    def _process_element(self, elem):
        lname = local_name(elem)

        # Limpa caracteres inválidos em XML
        if elem.text:
            elem.text = strip_xml_control_chars(elem.text)
        if elem.tail:
            elem.tail = strip_xml_control_chars(elem.tail)

        # <font> → <span>
        if lname == "font":
            self._convert_font_to_span(elem)
            lname = "span"

        # Limpa atributos não permitidos
        self._clean_attributes(elem, lname)

        # <br>: sem texto, sem style
        if lname == "br":
            elem.text = None
            elem.attrib.pop("style", None)

        # Recursão
        for child in list(elem):
            self._process_element(child)

    # ------------------------------------------------------------------
    # Split inteligente de <p> com blocos — lógica do v1
    # ------------------------------------------------------------------

    def _fix_block_in_p(self, parent) -> int:
        fixes = 0
        i = 0
        p_tag_ns = f"{{{XHTML_NS_URL}}}p"
        while i < len(parent):
            child = parent[i]
            fixes += self._fix_block_in_p(child)
            lname_child = local_name(child)
            if child.tag == p_tag_ns or lname_child == "p":
                has_block_child = any(local_name(gc) in BLOCK_TAGS for gc in child)
                if has_block_child:
                    replacements = self._split_p_around_blocks(child)
                    parent.remove(child)
                    for offset, elem in enumerate(replacements):
                        parent.insert(i + offset, elem)
                    fixes += 1
                    continue
            i += 1
        return fixes

    def _split_p_around_blocks(self, p_elem) -> list:
        result = []
        ns = f"{{{XHTML_NS_URL}}}"

        def new_p():
            el = etree.Element(p_elem.tag)
            for k, v in p_elem.attrib.items():
                el.set(k, v)
            return el

        current_p = new_p()
        current_p.text = p_elem.text

        for child in list(p_elem):
            if local_name(child) in BLOCK_TAGS:
                if self._p_has_content(current_p):
                    result.append(current_p)
                tail_text = child.tail
                child.tail = None
                result.append(child)
                current_p = new_p()
                current_p.text = tail_text
            else:
                current_p.append(child)

        if self._p_has_content(current_p):
            result.append(current_p)

        return result

    @staticmethod
    def _p_has_content(p_elem) -> bool:
        has_text = bool(p_elem.text and p_elem.text.strip())
        has_children = len(p_elem) > 0
        return has_text or has_children

    # ------------------------------------------------------------------
    # <font> → <span>
    # ------------------------------------------------------------------

    def _convert_font_to_span(self, font_elem):
        ns = f"{{{XHTML_NS_URL}}}"
        font_elem.tag = f"{ns}span"
        styles = []
        color = font_elem.get("color")
        if color:
            styles.append(f"color:{color}")
        face = font_elem.get("face")
        if face:
            styles.append(f"font-family:{face}")
        size = font_elem.get("size")
        if size:
            size_map = {"1": "0.6em", "2": "0.8em", "3": "1em",
                        "4": "1.1em", "5": "1.4em", "6": "1.8em", "7": "2.5em"}
            styles.append(f"font-size:{size_map.get(size, size)}")
        for attr in ("color", "face", "size"):
            font_elem.attrib.pop(attr, None)
        if styles:
            existing = font_elem.get("style", "")
            combined = (existing.rstrip(";") + ";" if existing else "") + ";".join(styles)
            font_elem.set("style", combined)

    # ------------------------------------------------------------------
    # Limpeza de atributos
    # ------------------------------------------------------------------

    def _clean_attributes(self, elem, lname: str):
        attribs = dict(elem.attrib)
        for attr, val in attribs.items():
            local_attr = attr.split("}", 1)[-1] if "}" in attr else attr

            # Remove xmlns redundantes
            if attr.startswith("xmlns"):
                del elem.attrib[attr]
                continue

            # Atributos globalmente proibidos
            # Exceção: 'name' em <object> não deve ser removido.
            # Na v1, 'name' só é removido de <a>; em <object>, pode ser
            # necessário para identificar referências de artefatos aninhados.
            if local_attr in ATTRS_TO_REMOVE:
                if local_attr == "name" and lname == "object":
                    continue  # preserva name em <object> (artefato aninhado)
                del elem.attrib[attr]
                continue

            # Atributos específicos por tag
            if lname == "table":
                if local_attr == "bgcolor":
                    self._add_style(elem, f"background-color:{val}")
                    del elem.attrib[attr]
                elif local_attr == "border":
                    self._add_style(elem, f"border:{val}px solid")
                    del elem.attrib[attr]
                elif local_attr == "cellpadding":
                    self._add_style(elem, f"border-spacing:{val}px")
                    del elem.attrib[attr]
                elif local_attr == "cellspacing":
                    self._add_style(elem, f"border-collapse:separate;border-spacing:{val}px")
                    del elem.attrib[attr]
                elif local_attr == "width":
                    self._add_style(elem, f"width:{val}px" if val.isdigit() else f"width:{val}")
                    del elem.attrib[attr]

            if lname in ("td", "th"):
                if local_attr == "bgcolor":
                    self._add_style(elem, f"background-color:{val}")
                    del elem.attrib[attr]
                elif local_attr == "width":
                    self._add_style(elem, f"width:{val}px" if val.isdigit() else f"width:{val}")
                    del elem.attrib[attr]
                elif local_attr == "height":
                    self._add_style(elem, f"height:{val}px" if val.isdigit() else f"height:{val}")
                    del elem.attrib[attr]
                elif local_attr == "align":
                    self._add_style(elem, f"text-align:{val}")
                    del elem.attrib[attr]

            # Limpa style: remove propriedades vendor/mso
            if attr == "style":
                clean = self._clean_style(val)
                if clean:
                    elem.set("style", clean)
                else:
                    del elem.attrib[attr]

    @staticmethod
    def _clean_style(style_val: str) -> str:
        if not style_val:
            return ""
        parts = [p.strip() for p in style_val.split(";") if p.strip()]
        clean_parts = []
        for part in parts:
            prop = part.split(":")[0].strip().lower()
            if prop.startswith(("mso-", "-webkit-", "-moz-", "-o-", "-ms-")):
                continue
            if prop in ("font-variant", "text-autospace", "text-kashida-space",
                        "punctuation-wrap", "text-underline", "text-align-last"):
                continue
            clean_parts.append(part)
        return "; ".join(clean_parts)

    @staticmethod
    def _add_style(elem, new_style: str):
        existing = elem.get("style", "")
        if existing and not existing.endswith(";"):
            existing += ";"
        elem.set("style", existing + new_style)


# ===========================================================================
# ReqIFZConverter — pipeline principal
# ===========================================================================

class ReqIFZConverter:

    def __init__(self, input_path: str, output_path: str):
        self.input_path = input_path
        self.output_path = output_path
        self.extracted_images: dict = {}

    def convert(self):
        log.info("Abrindo arquivo de entrada: %s", self.input_path)

        with zipfile.ZipFile(self.input_path, "r") as zin:
            namelist = zin.namelist()
            zip_filenames_lower = {n.replace("\\", "/").lower() for n in namelist}

            # Monta file_map: nome_arquivo → caminho_relativo (para v1-5)
            file_map = {}
            for name in namelist:
                norm = name.replace("\\", "/")
                basename = norm.split("/")[-1]
                if not basename.lower().endswith((".reqif", ".xml")):
                    file_map[basename] = norm
                    file_map[os.path.splitext(basename)[0]] = norm

            reqif_files = [n for n in namelist if n.lower().endswith(".reqif")]
            if not reqif_files:
                reqif_files = [n for n in namelist
                               if n.lower().endswith(".xml") and "reqif" in n.lower()]
            if not reqif_files:
                log.error("Nenhum arquivo .reqif encontrado no ZIP.")
                sys.exit(1)

            log.info("Arquivos .reqif encontrados: %s", reqif_files)

            processed: dict = {}
            for reqif_name in reqif_files:
                raw = zin.read(reqif_name)
                raw = self._fix_raw_xml(raw)
                converted_xml = self._convert_reqif(raw, zip_filenames_lower, file_map)
                processed[reqif_name] = converted_xml

            log.info("Gerando arquivo de saída: %s", self.output_path)
            with zipfile.ZipFile(self.output_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                processed_norm = {r.replace("\\", "/") for r in processed}
                for name in namelist:
                    norm = name.replace("\\", "/")
                    if norm in processed_norm:
                        zout.writestr(name, processed[name])
                        log.info("Arquivo convertido adicionado: %s", name)
                    else:
                        zout.writestr(name, zin.read(name))

                for img_name, img_bytes in self.extracted_images.items():
                    zout.writestr(img_name, img_bytes)
                    log.info("Imagem extraída adicionada ao ZIP: %s", img_name)

        log.info("Conversão concluída com sucesso.")

    # ------------------------------------------------------------------
    # Pré-processamento raw
    # ------------------------------------------------------------------

    def _fix_raw_xml(self, raw: bytes) -> bytes:
        text = raw.decode("utf-8", errors="replace")
        text = text.lstrip("\ufeff")
        decls = list(re.finditer(r"<\?xml[^?]*\?>", text))
        if len(decls) > 1:
            log.warning("Declarações XML duplicadas encontradas; removendo extras.")
            for decl in reversed(decls[1:]):
                text = text[:decl.start()] + text[decl.end():]
        text = strip_xml_control_chars(text)
        return text.encode("utf-8")

    # ------------------------------------------------------------------
    # Conversão principal
    # ------------------------------------------------------------------

    def _convert_reqif(self, xml_bytes: bytes, zip_filenames_lower: set, file_map: dict) -> bytes:
        try:
            parser = etree.XMLParser(
                remove_blank_text=False,
                resolve_entities=False,
                recover=True,
            )
            tree = etree.parse(io.BytesIO(xml_bytes), parser)
            root = tree.getroot()
        except etree.XMLSyntaxError as exc:
            log.error("Erro ao fazer parse do XML: %s", exc)
            sys.exit(1)

        # ── Regras do v1 (nível de documento) ──────────────────────────
        fix_header(root)
        fix_duplicate_ids_and_anchors(root)
        fix_duplicate_reqif_identifiers(root)
        fix_datatype_real(root)
        fix_thead_to_tbody(root)  # <thead>/<tfoot> → <tbody> (ELM 7.2 schema)

        # ── Lógica de mídia avançada (v1-5 + extração base64 do v2) ────
        fix_media_elements(root, file_map, self.extracted_images)

        # ── Limpeza XHTML por elemento (v2 + complemento v1) ───────────
        fixer = XHTMLFixer(zip_filenames_lower)
        for avx in root.xpath("//*[local-name()='ATTRIBUTE-VALUE-XHTML']"):
            for tv in avx.xpath("*[local-name()='THE-VALUE']"):
                fixer.fix_xhtml_value(tv)

        # ── Atributos proibidos por tag (varredura global v1-4) ─────────
        fix_prohibited_attrs(root)

        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )


# ===========================================================================
# CLI
# ===========================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Converte ReqIFZ do IBM Doors Next Generation 6.0.4 "
            "para o formato compatível com o IBM ELM 7.2."
        ),
    )
    parser.add_argument("input", help="Arquivo .reqifz de entrada.")
    parser.add_argument(
        "output",
        nargs="?",
        help="Arquivo .reqifz de saída. Padrão: <entrada>_elm72.reqifz",
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Ativa saída detalhada.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)

    input_path = args.input
    if not os.path.isfile(input_path):
        log.error("Arquivo de entrada não encontrado: %s", input_path)
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_elm72{ext}"

    converter = ReqIFZConverter(input_path, output_path)
    converter.convert()
    print(f"\nArquivo convertido gerado: {output_path}")


if __name__ == "__main__":
    main()
