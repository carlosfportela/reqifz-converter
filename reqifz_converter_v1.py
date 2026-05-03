# =====================================================
# ReqIF Converter v1.1.3
#
# 30/04/2026
#
# Pra que serve:
# - Converte arquivos .reqifz gerados no DOORS v6 para o formato compatível com o DOORS v7
# Pré-requisitos:
# - Compatível com Python v3.8+
# - Usa apenas bibliotecas padrão + lxml (pip install lxml)
# Como usar:
# - Comando: python reqifconverter.py arquivo.reqifz
# =====================================================
import zipfile
import os
import shutil
import argparse
from lxml import etree
def patch_reqif_xml(xml_path, file_map):
 
    parser = etree.XMLParser(recover=True, remove_blank_text=True)
    try:
        tree = etree.parse(xml_path, parser)
        root = tree.getroot()
    except Exception as e:
        print(f"  [Erro] Falha ao processar {xml_path}: {e}")
        return
    ns = {'reqif': 'http://www.omg.org/spec/ReqIF/20110401/reqif.xsd'}
    xhtml_ns = "http://www.w3.org/1999/xhtml"
    nsmap = {
        "rm": "http://www.ibm.com/rm"
    }
 

    # 1. Limpeza de Header
    header = root.find('.//reqif:REQ-IF-HEADER', ns)
    if header is not None:
        for child in header.getchildren():
            if not child.tag.startswith(f"{{{ns['reqif']}}}"):
                header.remove(child)
        tid = header.find('reqif:TOOL-ID', ns)
        if tid is not None:
            tid.text = "IBM Engineering Requirements Management DOORS Next (v7.2)"
    # 2. Correção de IDs Duplicados, Atributo 'name' em <a> e Remoção de <button>
    seen_ids = set()
    # Adicionado //xhtml:button para tratamento
    for elem in root.xpath("//*[@id] | //xhtml:a | //xhtml:button", namespaces={'xhtml': xhtml_ns}):
        tag_local = etree.QName(elem).localname
 
        # --- AJUSTE: Remoção de elemento <button> proibido ---
        if tag_local == 'button':
            parent = elem.getparent()
            if elem.text:
                # Transfere o texto do botão para o elemento pai antes de remover
                if parent.text: parent.text += elem.text
                else: parent.text = elem.text
            parent.remove(elem)
            continue
        # ----------------------------------------------------
 
        # Tratar atributo 'name' em links (erro cvc-complex-type.3.2.2)
        if tag_local == 'a' and elem.get('name') is not None:
            if elem.get('id') is None:
                elem.set('id', elem.get('name'))
            del elem.attrib['name']
        # Verificar IDs duplicados
        current_id = elem.get("id")
        if current_id:
            if current_id in seen_ids:
                del elem.attrib["id"]
            else:
                seen_ids.add(current_id)
    # 3. Corrigir DATATYPE-DEFINITION-REAL (Regra preservada conforme sua versão)
    for real in root.xpath(".//reqif:DATATYPE-DEFINITION-REAL", namespaces=ns):
        if "MIN" not in real.attrib:
            real.attrib["MIN"] = "-1.0E308"
        if "MAX" not in real.attrib:
            real.attrib["MAX"] = "1.0E308"
    # 4. Correção de Atributos Proibidos
    for elem in root.xpath("//xhtml:*", namespaces={'xhtml': xhtml_ns}):
        tag_local = etree.QName(elem).localname
        if tag_local == 'ol' and elem.get('start') is not None:
            del elem.attrib['start']
        if tag_local == 'br' and elem.get('style') is not None:
            del elem.attrib['style']
        if tag_local == 'table' and elem.get('align') is not None:
            del elem.attrib['align']
        for attr in ['lang', 'dir', 'valign']:
            if elem.get(attr) is not None:
                del elem.attrib[attr]
    # 5. Lógica de Mídia (Regra de rm:CONTENT-TYPE preservada)
    for elem in root.xpath("//xhtml:object | //xhtml:img", namespaces={'xhtml': xhtml_ns}):
        is_img = 'img' in elem.tag
        attr = 'src' if is_img else 'data'
        val = elem.get(attr)
        if val:
            resource_id = val.split('?')[0].replace("\\", "/").split('/')[-1]
            resource_id_no_ext = os.path.splitext(resource_id)[0]
            target_file = file_map.get(resource_id) or file_map.get(resource_id_no_ext)
            if target_file:
                if is_img:
                    new_obj = etree.Element(f"{{{xhtml_ns}}}object")
                    new_obj.set("data", target_file)
                    content_type = None
 
                    wrapped = root.xpath(
                        f".//rm:WRAPPED-RESOURCE[@IDENTIFIER='{target_file}']/rm:CONTENT-TYPE",
                        namespaces=nsmap
                    )
 
                    if wrapped:
                        content_type = wrapped[0].text
 
                    new_obj.set(
                        "type",
                        content_type or "application/octet-stream"
                    )
 
                    if elem.get('style'): new_obj.set('style', elem.get('style'))
                    new_obj.text = target_file
                    elem.getparent().replace(elem, new_obj)
                else:
                    elem.set("data", target_file)
            # --- AJUSTE: Se for img e não achou o arquivo, remove para não quebrar o esquema ---
            elif is_img:
                elem.getparent().remove(elem)
            # ---------------------------------------------------------------------------------
    tree.write(xml_path, encoding='UTF-8', xml_declaration=True, pretty_print=True)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename")
    args = parser.parse_args()
    input_file = args.filename
    if not input_file.lower().endswith('.reqifz'): return
    output_file = input_file.replace(".reqifz", "_v7.reqifz")
    temp_dir = "migration_v4_idfix"
    if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    try:
        with zipfile.ZipFile(input_file, 'r') as z:
            z.extractall(temp_dir)
        file_map = {}
        for r, d, f in os.walk(temp_dir):
            for file in f:
                if not file.lower().endswith(('.reqif', '.xml')):
                    rel_path = os.path.relpath(os.path.join(r, file), temp_dir).replace("\\", "/")
                    file_map[file] = rel_path
                    file_map[os.path.splitext(file)[0]] = rel_path
        for r, d, f in os.walk(temp_dir):
            for file in f:
                if file.lower().endswith(('.reqif', '.xml')):
                    patch_reqif_xml(os.path.join(r, file), file_map)
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as z_out:
            for r, d, f in os.walk(temp_dir):
                for file in f:
                    fp = os.path.join(r, file)
                    z_out.write(fp, os.path.relpath(fp, temp_dir))
        print(f"[OK] Conversão concluída. Arquivo gerado: {output_file}")
    finally:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
if __name__ == "__main__":
    main()