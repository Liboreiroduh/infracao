#!/usr/bin/env python3
import html
import re
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from zipfile import ZIP_DEFLATED, ZipFile


DEFAULT_CODES = {"7471", "7579", "5169"}
PLATE_RE = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
CODE_CELL_RE = re.compile(r"^(?P<code>\d{4})(?:-\d+)?$")


@dataclass(frozen=True)
class TextItem:
    page: int
    x: float
    y: float
    text: str


@dataclass(frozen=True)
class ColumnLayout:
    ranges: dict[str, tuple[float, float]]


def parse_codes(raw_codes: str | Iterable[str]) -> list[str]:
    if isinstance(raw_codes, str):
        chunks = re.split(r"[,\s;]+", raw_codes)
    else:
        chunks = list(raw_codes)

    normalized: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        digits = re.sub(r"\D", "", chunk or "")
        if len(digits) < 4:
            continue
        code = digits[:4]
        if code not in seen:
            seen.add(code)
            normalized.append(code)
    if not normalized:
        raise ValueError("Informe pelo menos um código com 4 dígitos.")
    return normalized


def extract_records_from_path(pdf_path: Path | str, target_codes: Sequence[str] | str) -> list[tuple[str, str, str]]:
    return extract_records_from_bytes(Path(pdf_path).read_bytes(), target_codes)


def extract_records_from_bytes(pdf_bytes: bytes, target_codes: Sequence[str] | str) -> list[tuple[str, str, str]]:
    normalized_codes = set(parse_codes(target_codes))
    objects = read_pdf_objects(pdf_bytes)
    page_ids = extract_pages(objects)
    records: list[tuple[str, str, str]] = []
    layout: ColumnLayout | None = None

    for page_number, page_id in enumerate(page_ids, start=1):
        page_items = extract_page_items(objects, page_id, page_number)
        rows = group_rows(page_items)
        layout = detect_layout(rows, layout)
        for row in rows:
            if is_header_row(row):
                continue
            record = row_to_record(row, layout)
            if record and record[1] in normalized_codes:
                records.append(record)

    return records


def debug_page_from_path(pdf_path: Path | str, page_number: int) -> list[str]:
    objects = read_pdf_objects(Path(pdf_path).read_bytes())
    page_ids = extract_pages(objects)
    if page_number < 1 or page_number > len(page_ids):
        raise ValueError(f"Página inválida: {page_number}")
    page_items = extract_page_items(objects, page_ids[page_number - 1], page_number)
    lines: list[str] = []
    for row in group_rows(page_items):
        rendered = " | ".join(f"{item.x:7.2f}:{item.text}" for item in row)
        lines.append(f"{row[0].y:8.2f} | {rendered}")
    return lines


def write_xlsx(output_path: Path | str, records: list[tuple[str, str, str]]) -> None:
    Path(output_path).write_bytes(build_xlsx_bytes(records))


def build_xlsx_bytes(records: list[tuple[str, str, str]]) -> bytes:
    import io

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="autuacoes" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        '</Relationships>'
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font>'
        '</fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )

    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", build_sheet_xml(records))
    return buffer.getvalue()


def read_pdf_objects(data: bytes) -> dict[int, bytes]:
    objects: dict[int, bytes] = {}
    for match in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", data, re.S):
        objects[int(match.group(1))] = match.group(2)
    if not objects:
        raise ValueError("Não foi possível ler a estrutura do PDF.")
    return objects


def extract_pages(objects: dict[int, bytes]) -> list[int]:
    catalog = find_catalog_object(objects)
    pages_ref = re.search(rb"/Pages\s+(\d+)\s+0\s+R", catalog)
    if not pages_ref:
        raise ValueError("Referência /Pages não encontrada no catálogo.")
    return collect_page_ids(objects, int(pages_ref.group(1)))


def find_catalog_object(objects: dict[int, bytes]) -> bytes:
    for obj in objects.values():
        if re.search(rb"/Type\s*/Catalog\b", obj):
            return obj
    raise ValueError("Objeto /Catalog não encontrado.")


def collect_page_ids(objects: dict[int, bytes], object_id: int) -> list[int]:
    obj = objects.get(object_id)
    if obj is None:
        raise ValueError(f"Objeto {object_id} não encontrado na árvore de páginas.")
    if re.search(rb"/Type\s*/Page\b", obj):
        return [object_id]
    if not re.search(rb"/Type\s*/Pages\b", obj):
        raise ValueError(f"Objeto {object_id} não é /Page nem /Pages.")

    kids = re.search(rb"/Kids\s*\[(.*?)\]", obj, re.S)
    if not kids:
        raise ValueError("Lista /Kids não encontrada.")

    page_ids: list[int] = []
    for kid in re.findall(rb"(\d+)\s+0\s+R", kids.group(1)):
        page_ids.extend(collect_page_ids(objects, int(kid)))
    return page_ids


def extract_page_items(objects: dict[int, bytes], page_id: int, page_number: int) -> list[TextItem]:
    page_obj = objects[page_id]
    content_refs = [int(num) for num in re.findall(rb"/Contents\s+(\d+)\s+0\s+R", page_obj)]
    if not content_refs:
        array_match = re.search(rb"/Contents\s*\[(.*?)\]", page_obj, re.S)
        if array_match:
            content_refs = [int(num) for num in re.findall(rb"(\d+)\s+0\s+R", array_match.group(1))]

    items: list[TextItem] = []
    for ref in content_refs:
        items.extend(extract_text_items(extract_stream(objects[ref]), page_number))
    return items


def extract_stream(obj: bytes) -> bytes:
    match = re.search(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", obj, re.S)
    if not match:
        return b""
    header = match.group(1)
    raw_stream = match.group(2)
    if b"/FlateDecode" in header:
        return zlib.decompress(raw_stream)
    return raw_stream


def decode_literal(data: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        if byte != 0x5C:
            out.append(byte)
            i += 1
            continue

        i += 1
        if i >= len(data):
            break
        esc = data[i]
        mapping = {
            ord("n"): 10,
            ord("r"): 13,
            ord("t"): 9,
            ord("b"): 8,
            ord("f"): 12,
            ord("("): 40,
            ord(")"): 41,
            ord("\\"): 92,
        }
        if esc in mapping:
            out.append(mapping[esc])
            i += 1
            continue
        if 48 <= esc <= 55:
            oct_digits = bytearray([esc])
            i += 1
            for _ in range(2):
                if i < len(data) and 48 <= data[i] <= 55:
                    oct_digits.append(data[i])
                    i += 1
                else:
                    break
            out.append(int(oct_digits.decode("ascii"), 8))
            continue
        if esc in (10, 13):
            if esc == 13 and i + 1 < len(data) and data[i + 1] == 10:
                i += 1
            i += 1
            continue

        out.append(esc)
        i += 1
    return out.decode("cp1252", "replace")


def decode_hex(data: bytes) -> str:
    hex_text = re.sub(rb"\s+", b"", data)
    if len(hex_text) % 2:
        hex_text += b"0"
    return bytes.fromhex(hex_text.decode("ascii")).decode("cp1252", "replace")


def tokenize_pdf_content(data: bytes) -> Iterable[object]:
    i = 0
    length = len(data)
    whitespace = b" \t\r\n\x0c\x00"
    delimiters = b"[]<>()/"

    while i < length:
        byte = data[i]

        if byte in whitespace:
            i += 1
            continue
        if byte == 0x25:
            while i < length and data[i] not in (10, 13):
                i += 1
            continue
        if byte == 0x28:
            depth = 1
            i += 1
            buf = bytearray()
            while i < length and depth:
                current = data[i]
                if current == 0x5C:
                    buf.append(current)
                    i += 1
                    if i < length:
                        buf.append(data[i])
                        i += 1
                    continue
                if current == 0x28:
                    depth += 1
                elif current == 0x29:
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                if depth:
                    buf.append(current)
                i += 1
            yield ("string", decode_literal(bytes(buf)))
            continue
        if data[i : i + 2] == b"<<":
            yield "<<"
            i += 2
            continue
        if data[i : i + 2] == b">>":
            yield ">>"
            i += 2
            continue
        if byte == 0x3C:
            j = data.find(b">", i + 1)
            if j == -1:
                raise ValueError("Hex string inválida.")
            yield ("string", decode_hex(data[i + 1 : j]))
            i = j + 1
            continue
        if byte in (0x5B, 0x5D):
            yield chr(byte)
            i += 1
            continue
        if byte == 0x2F:
            j = i + 1
            while j < length and data[j] not in whitespace + delimiters:
                j += 1
            yield ("name", data[i + 1 : j].decode("latin1"))
            i = j
            continue

        j = i
        while j < length and data[j] not in whitespace + delimiters:
            j += 1
        token = data[i:j].decode("latin1")
        if re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", token):
            yield float(token)
        else:
            yield token
        i = j


def decode_tj_array(values: list[object]) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, tuple) and value[0] == "string":
            parts.append(value[1])
    return "".join(parts).strip()


def extract_text_items(stream: bytes, page_number: int) -> list[TextItem]:
    tokens = list(tokenize_pdf_content(stream))
    items: list[TextItem] = []
    stack: list[object] = []
    array_stack: list[list[object]] = []
    text_x = 0.0
    text_y = 0.0
    leading = 0.0
    in_text = False

    def emit_text(text: str) -> None:
        cleaned = normalize_whitespace(text)
        if cleaned:
            items.append(TextItem(page=page_number, x=text_x, y=text_y, text=cleaned))

    for token in tokens:
        if token == "BT":
            in_text = True
            stack.clear()
            array_stack.clear()
            text_x = 0.0
            text_y = 0.0
            continue
        if token == "ET":
            in_text = False
            stack.clear()
            array_stack.clear()
            continue
        if not in_text:
            continue

        if token == "[":
            array_stack.append([])
            continue
        if token == "]":
            values = array_stack.pop() if array_stack else []
            if array_stack:
                array_stack[-1].append(values)
            else:
                stack.append(values)
            continue

        if array_stack:
            array_stack[-1].append(token)
            continue

        if isinstance(token, str):
            if token == "Tm" and len(stack) >= 6:
                text_x = float(stack[-2])
                text_y = float(stack[-1])
                stack.clear()
                continue
            if token in {"Td", "TD"} and len(stack) >= 2:
                text_x += float(stack[-2])
                text_y += float(stack[-1])
                if token == "TD":
                    leading = -float(stack[-1])
                stack.clear()
                continue
            if token == "TL" and stack:
                leading = float(stack[-1])
                stack.clear()
                continue
            if token == "T*" and leading:
                text_y -= leading
                stack.clear()
                continue
            if token == "Tj" and stack:
                value = stack.pop()
                if isinstance(value, tuple) and value[0] == "string":
                    emit_text(value[1])
                stack.clear()
                continue
            if token == "TJ" and stack:
                value = stack.pop()
                if isinstance(value, list):
                    emit_text(decode_tj_array(value))
                stack.clear()
                continue
            if token == "'" and stack:
                text_y -= leading
                value = stack.pop()
                if isinstance(value, tuple) and value[0] == "string":
                    emit_text(value[1])
                stack.clear()
                continue
            if token == '"' and len(stack) >= 3:
                text_y -= leading
                value = stack.pop()
                if isinstance(value, tuple) and value[0] == "string":
                    emit_text(value[1])
                stack.clear()
                continue
            if token in {
                "Tc",
                "Tw",
                "Tz",
                "Ts",
                "Tf",
                "Tr",
                "cm",
                "rg",
                "g",
                "G",
                "w",
                "J",
                "j",
                "M",
                "d",
                "m",
                "l",
                "h",
                "f",
                "S",
                "n",
                "q",
                "Q",
                "re",
                "W",
                "Do",
            }:
                stack.clear()
                continue

        stack.append(token)

    return items


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def group_rows(items: list[TextItem]) -> list[list[TextItem]]:
    rows: list[list[TextItem]] = []
    current: list[TextItem] = []
    current_y: float | None = None
    tolerance = 1.5

    for item in sorted(items, key=lambda row: (-row.y, row.x)):
        if current_y is None or abs(item.y - current_y) <= tolerance:
            current.append(item)
            current_y = item.y if current_y is None else current_y
            continue
        rows.append(sorted(current, key=lambda row: row.x))
        current = [item]
        current_y = item.y

    if current:
        rows.append(sorted(current, key=lambda row: row.x))
    return rows


def detect_layout(rows: list[list[TextItem]], previous: ColumnLayout | None) -> ColumnLayout | None:
    for row in rows:
        layout = build_layout_from_header_row(row)
        if layout is not None:
            return layout
    return previous


def build_layout_from_header_row(row: list[TextItem]) -> ColumnLayout | None:
    if not row:
        return None

    kinds = {kind for item in row if (kind := classify_header_label(item.text))}
    if not {"plate", "date", "code"}.issubset(kinds):
        return None

    ordered = sorted(row, key=lambda item: item.x)
    ranges: dict[str, tuple[float, float]] = {}
    for index, item in enumerate(ordered):
        kind = classify_header_label(item.text)
        if kind is None:
            continue
        left = 0.0 if index == 0 else midpoint(ordered[index - 1].x, item.x)
        right = float("inf") if index == len(ordered) - 1 else midpoint(item.x, ordered[index + 1].x)
        ranges[kind] = (left, right)

    if {"plate", "date", "code"}.issubset(ranges):
        return ColumnLayout(ranges=ranges)
    return None


def midpoint(left: float, right: float) -> float:
    return (left + right) / 2.0


def is_header_row(row: list[TextItem]) -> bool:
    return build_layout_from_header_row(row) is not None


def row_to_record(row: list[TextItem], layout: ColumnLayout | None) -> tuple[str, str, str] | None:
    if not row or layout is None:
        return None

    plate_range = layout.ranges.get("plate")
    date_range = layout.ranges.get("date")
    code_range = layout.ranges.get("code")
    if plate_range is None or date_range is None or code_range is None:
        return None

    plate = next(
        (
            cleaned
            for item in row
            for cleaned in [clean_plate(item.text)]
            if plate_range[0] <= item.x <= plate_range[1]
            and PLATE_RE.fullmatch(cleaned)
        ),
        None,
    )
    date = next(
        (
            item.text
            for item in row
            if date_range[0] <= item.x <= date_range[1] and DATE_RE.fullmatch(item.text)
        ),
        None,
    )
    code = next(
        (
            parsed_code
            for item in row
            for parsed_code in [parse_code_cell(item.text)]
            if code_range[0] <= item.x <= code_range[1] and parsed_code is not None
        ),
        None,
    )
    if plate and date and code:
        return plate, code, date
    return None


def clean_plate(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def parse_code_cell(text: str) -> str | None:
    match = CODE_CELL_RE.fullmatch(normalize_whitespace(text))
    if not match:
        return None
    return match.group("code")


def normalize_label(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return normalize_whitespace(without_accents).casefold()


def classify_header_label(text: str) -> str | None:
    normalized = normalize_label(text)

    if normalized == "placa" or normalized.startswith("placa "):
        return "plate"
    if normalized in {"data", "dt"}:
        return "date"
    if normalized == "infracao":
        return "code"
    if normalized.startswith("infracao/") or normalized.startswith("infracao "):
        return "code"
    if "codigo" in normalized and "infracao" in normalized:
        return "code"
    if normalized.startswith("cod ") and "infracao" in normalized:
        return "code"
    if "data" in normalized and "infracao" in normalized:
        return "date"
    if "numero" in normalized and "auto" in normalized:
        return "auto"
    if normalized.startswith("auto"):
        return "auto"
    if "data" in normalized and ("limite" in normalized or "vencimento" in normalized):
        return "limit"
    return None


def col_ref(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def xml_escape(text: str) -> str:
    return html.escape(text, quote=False)


def build_sheet_xml(records: list[tuple[str, str, str]]) -> str:
    rows_xml: list[str] = []
    headers = ["placa", "autuacao", "data"]
    all_rows = [headers] + [list(record) for record in records]

    for row_number, row in enumerate(all_rows, start=1):
        cells: list[str] = []
        style_id = "1" if row_number == 1 else "0"
        for column_number, value in enumerate(row, start=1):
            ref = f"{col_ref(column_number)}{row_number}"
            cells.append(
                f'<c r="{ref}" s="{style_id}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>'
            )
        rows_xml.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        '<cols>'
        '<col min="1" max="1" width="14" customWidth="1"/>'
        '<col min="2" max="2" width="12" customWidth="1"/>'
        '<col min="3" max="3" width="14" customWidth="1"/>'
        '</cols>'
        f'<sheetData>{"".join(rows_xml)}</sheetData>'
        '</worksheet>'
    )
