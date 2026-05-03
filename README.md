# ReqIFZ Converter — DNG 6.0.4 → IBM ELM 7.2

Utilitário Python que converte arquivos `.reqifz` exportados do **IBM Doors Next Generation 6.0.4** para um formato compatível com o **IBM Engineering Lifecycle Management (ELM) 7.2**.

## Instalação

```bash
pip install lxml
```

## Uso

```bash
# Gera automaticamente <arquivo>_elm72.reqifz
python reqifz_converter.py meu_modulo.reqifz

# Especifica o arquivo de saída
python reqifz_converter.py meu_modulo.reqifz meu_modulo_elm72.reqifz

# Modo verbose (detalhado)
python reqifz_converter.py -v meu_modulo.reqifz
```

## Incompatibilidades tratadas

| # | Problema | Ação |
|---|----------|------|
| 1 | `<p>` envolvendo elementos de bloco (`<table>`, `<ul>`, `<ol>`, `<div>`, …) | Remove o `<p>` envoltório, promovendo os filhos ao nível pai |
| 2 | Atributo `class` em elementos `reqif-xhtml` | Removido |
| 3 | Atributo `lang` / `dir` | Removidos |
| 4 | Atributo `style` com propriedades `mso-*`, `-webkit-*`, `-moz-*` (resíduos do MS Word) | Propriedades proprietárias removidas; propriedades CSS padrão mantidas |
| 5 | Atributos de apresentação HTML4 em `<table>`: `align`, `bgcolor`, `border`, `cellpadding`, `cellspacing`, `width` | Convertidos para CSS inline via atributo `style` |
| 6 | Atributos de apresentação HTML4 em `<td>`/`<th>`: `bgcolor`, `width`, `height`, `align` | Convertidos para CSS inline via `style` |
| 7 | Tag `<img src="...">` | Convertida para `<object data="..." type="...">` conforme especificação ReqIF |
| 8 | Imagem embutida como `data:image/...;base64,...` em `<img src>` | Decodificada, salva como arquivo separado no ZIP e referenciada por caminho relativo |
| 9 | Tag `<font color="..." face="..." size="...">` | Convertida para `<span style="...">` |
| 10 | Caminhos de imagem com `\` (Windows) | Normalizados para `/` |
| 11 | Caracteres de controle inválidos em XML 1.0 (exceto TAB, LF, CR) | Removidos |
| 12 | Declarações `<?xml ...?>` duplicadas | Extras removidas |
| 13 | Atributos `xmlns` redundantes em elementos filhos | Removidos (gerenciados pelo lxml) |
| 14 | Atributos `name`, `target`, `rel` em `<a>` | Removidos |
| 15 | Atributos `hspace`, `vspace`, `border`, `compact`, `nowrap`, `valign` | Removidos |

## Estrutura do ReqIFZ

Um `.reqifz` é um arquivo ZIP contendo:

```
meu_modulo.reqifz
├── meu_modulo.reqif          ← XML principal (modificado pelo converter)
├── imagem1.png               ← arquivos de imagem referenciados
├── imagem2.jpg
└── ...
```

Imagens extraídas de base64 são adicionadas à raiz do ZIP de saída.

## Limitações conhecidas

- Tabelas aninhadas são desaninhadas de forma conservadora; estruturas muito complexas podem precisar de revisão manual.
- Atributos `colspan` e `rowspan` são preservados (são válidos no XHTML ReqIF).
- O script não altera GUIDs, identificadores ou estrutura hierárquica dos requisitos.
- Não faz mapeamento de tipos de artefatos — apenas corrige a formatação XHTML.

## Verificação pós-conversão

Após a importação no ELM 7.2, verifique:
1. Se todos os artefatos com tabelas importaram corretamente.
2. Se as imagens são exibidas nos campos de texto enriquecido.
3. Se os atributos de enumeração foram mapeados corretamente.
