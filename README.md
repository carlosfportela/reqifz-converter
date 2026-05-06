# ReqIFZ Converter — IBM CLM RDNG → IBM ELM DOORS NEXT 7.2

Read this in other languages: [Português](README.pt-br.md)

Web application developed in Python (Flask) for batch conversion of `.reqifz` files. The tool adjusts packages exported from earlier versions of **IBM Doors Next Generation** into a strict format compatible with **IBM Engineering Lifecycle Management (ELM) 7.2**.

Note: Tests were successfully performed with reqifz files from RDNG 6.0.4.

## Current Features (Version 2.0 beta)

- **Modern Web Interface**: Intuitive interface with drag-and-drop support for multiple files and a "glassmorphism" theme.
- **Batch Conversion**: Process multiple `.reqifz` files simultaneously quickly and safely.
- **Algorithm Selection**: Choose directly in the interface which rule engine to use:
  - **v2 (Current Rules)**: More robust algorithm. Undoes severe invalid nesting (like tables inside paragraphs), handles images by converting base64 to physical files, and fixes dozens of tags not allowed by the ELM 7.2 specification.
  - **v1 (Original Rules)**: Legacy algorithm that handles ID duplication, removal of `<button>` elements, and basic attribute cleanup.
- **Logs Visualization**: Track the processing and possible warnings for each file in an embedded terminal on the screen.
- **Consolidated Download**: Download the converted packages individually or all at once grouped in a single `.zip` file.

## Installation

The application requires **Python 3.8+**.

1. Clone the repository or access the project folder.
2. It is recommended to create a virtual environment (venv):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/Mac:
   source venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## How to Run

To start the web application, run the command:

```bash
python app.py
```

Access the address in your browser: **http://localhost:5000**

> **Note:** The conversion script can still be executed via command line for use in automations:
> ```bash
> python reqifz_converter.py my_file.reqifz
> ```

## Handled Incompatibilities (Algorithm v2)

| # | Problem | Action |
|---|----------|------|
| 1 | `<p>` wrapping block elements (`<table>`, `<ul>`, `<ol>`, `<div>`, …) | Removes the wrapper `<p>`, promoting children to the parent level |
| 2 | `class` attribute in `reqif-xhtml` elements | Removed |
| 3 | `lang` / `dir` attribute | Removed |
| 4 | `style` attribute with `mso-*`, `-webkit-*`, `-moz-*` properties | Proprietary properties (Word/Browsers) removed; standard CSS properties kept |
| 5 | Presentation attributes in `<table>` (`align`, `bgcolor`, `width`, etc) | Converted to inline CSS via `style` attribute |
| 6 | Presentation attributes in `<td>`/`<th>` | Converted to inline CSS via `style` |
| 7 | `<img src="...">` tag | Converted to `<object data="..." type="...">` according to the original ReqIF specification |
| 8 | Image embedded as `data:image/...;base64,...` | Decoded, physically saved as PNG/JPG file in the ZIP root and correctly referenced |
| 9 | `<font>` tag | Converted to `<span style="...">` |
| 10| Image paths with `\` (Windows) | Normalized to `/` |
| 11| Invalid control characters in XML 1.0 | Removed |
| 12| Unsupported attributes in `<a>` (e.g., `name`) | Removed, promoted to `id` when necessary |
| 13| Duplicate `IDENTIFIER` attributes | Renames duplicate identifiers in content elements to ensure uniqueness and removes schema duplicates |

## Modified ReqIFZ Structure

A converted `.reqifz` is a valid ZIP file for ELM 7.2 containing:

```text
my_module_elm72.reqifz
├── my_module.reqif          ← Corrected, sanitized, and validated main XML
├── old_image.png            ← Image files that already existed in the package
├── extracted_img_abc123.png ← (New) Images extracted from base64 during conversion
└── ...
```

## Known Limitations

- Tables and lists that are very incorrectly nested in the original DNG are un-nested as much as possible, but extremely confusing structures may require visual review after import.
- The script strictly preserves GUIDs and the hierarchy of requirements so as not to break cross-references or links.
- Focuses on XHTML corrections; does not do "translation" of artifact types if they have changed name/ID on your destination server.

## Post-Conversion Verification

After importing into ELM 7.2, it is suggested to verify:
1. If rich artifacts (containing complex tables) imported without errors.
2. If images that were previously inserted via *copy and paste* in DNG 6 are displaying normally.
3. If the general flow did not present blocking *Warnings* in the Jazz server logs.
