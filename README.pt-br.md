# ReqIFZ Converter — IBM CLM RDNG  → IBM ELM DOORS NEXT 7.2

Leia isso em outros idiomas: [English](README.md)

Aplicação Web desenvolvida em Python (Flask) para conversão em lote de arquivos `.reqifz`. A ferramenta ajusta pacotes exportados de versões anteriores do **IBM Doors Next Generation** para um formato rigoroso compatível com o **IBM Engineering Lifecycle Management (ELM) 7.2**.

Nota: Os testes foram realizados com sucesso com o arquivos reqifz do RDNG 6.0.4.

## Recursos Atuais (Versão 2.0 beta)

- **Interface Web Moderna**: Interface intuitiva com suporte a drag-and-drop para múltiplos arquivos e tema "glassmorphism".
- **Conversão em Lote**: Processe vários arquivos `.reqifz` simultaneamente de forma rápida e segura.
- **Seleção de Algoritmo**: Escolha diretamente na interface qual motor de regras usar:
  - **v2 (Regras Atuais)**: Algoritmo mais robusto. Desfaz aninhamentos inválidos graves (como tabelas dentro de parágrafos), lida com imagens convertendo base64 para arquivos físicos e corrige dezenas de tags não permitidas pela especificação ELM 7.2.
  - **v1 (Regras Originais)**: Algoritmo legado que trata duplicação de IDs, remoção de elementos `<button>` e limpeza de atributos básicos.
- **Visualização de Logs**: Acompanhe o processamento e eventuais avisos de cada arquivo em um terminal embutido na tela.
- **Download Consolidado**: Baixe os pacotes convertidos individualmente ou todos de uma vez agrupados em um único arquivo `.zip`.

## Instalação

A aplicação requer **Python 3.8+**.

1. Clone o repositório ou acesse a pasta do projeto.
2. É recomendável criar um ambiente virtual (venv):
   ```bash
   python -m venv venv
   # No Windows:
   venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## Como Executar

Para iniciar a aplicação web, rode o comando:

```bash
python app.py
```

Acesse no seu navegador o endereço: **http://localhost:5000**

> **Nota:** O script de conversão continua podendo ser executado via linha de comando para uso em automações:
> ```bash
> python reqifz_converter.py meu_arquivo.reqifz
> ```

## Incompatibilidades tratadas (Algoritmo v2)

| # | Problema | Ação |
|---|----------|------|
| 1 | `<p>` envolvendo elementos de bloco (`<table>`, `<ul>`, `<ol>`, `<div>`, …) | Remove o `<p>` envoltório, promovendo os filhos ao nível pai |
| 2 | Atributo `class` em elementos `reqif-xhtml` | Removido |
| 3 | Atributo `lang` / `dir` | Removidos |
| 4 | Atributo `style` com propriedades `mso-*`, `-webkit-*`, `-moz-*` | Propriedades proprietárias (Word/Browsers) removidas; propriedades CSS padrão mantidas |
| 5 | Atributos de apresentação em `<table>` (`align`, `bgcolor`, `width`, etc) | Convertidos para CSS inline via atributo `style` |
| 6 | Atributos de apresentação em `<td>`/`<th>` | Convertidos para CSS inline via `style` |
| 7 | Tag `<img src="...">` | Convertida para `<object data="..." type="...">` conforme especificação ReqIF original |
| 8 | Imagem embutida como `data:image/...;base64,...` | Decodificada, salva fisicamente como arquivo PNG/JPG na raiz do ZIP e referenciada corretamente |
| 9 | Tag `<font>` | Convertida para `<span style="...">` |
| 10| Caminhos de imagem com `\` (Windows) | Normalizados para `/` |
| 11| Caracteres de controle inválidos em XML 1.0 | Removidos |
| 12| Atributos não suportados em `<a>` (ex: `name`) | Removidos, promovidos a `id` quando necessário |

## Estrutura do ReqIFZ Modificado

Um `.reqifz` convertido é um arquivo ZIP válido para o ELM 7.2 contendo:

```text
meu_modulo_elm72.reqifz
├── meu_modulo.reqif          ← XML principal corrigido, sanitizado e validado
├── imagem_antiga.png         ← Arquivos de imagem que já existiam no pacote
├── img_extraida_abc123.png   ← (Novo) Imagens extraídas do base64 durante a conversão
└── ...
```

## Limitações conhecidas

- Tabelas e listas muito aninhadas de forma incorreta no DNG original são desaninhadas o máximo possível, mas estruturas extremamente confusas podem precisar de revisão visual após a importação.
- O script preserva estritamente os GUIDs e a hierarquia dos requisitos para não quebrar referências cruzadas ou links.
- Foca-se em correções XHTML; não faz "tradução" de tipos de artefatos caso eles tenham mudado de nome/ID no seu servidor de destino.

## Verificação Pós-Conversão

Após realizar a importação no ELM 7.2, é sugerido verificar:
1. Se artefatos ricos (contendo tabelas complexas) importaram sem erros.
2. Se as imagens que antes eram inseridas via *copiar e colar* no DNG 6 estão aparecendo normalmente.
3. Se o fluxo geral não apresentou *Warnings* bloqueantes nos logs do servidor Jazz.
