#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from autuacao_extractor import DEFAULT_CODES, debug_page_from_path, extract_records_from_path, write_xlsx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="Edital_2026_Autuação_704.pdf")
    parser.add_argument("--xlsx", default="autuacoes_filtradas.xlsx")
    parser.add_argument("--codes", default=",".join(sorted(DEFAULT_CODES)))
    parser.add_argument("--debug-page", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"PDF não encontrado: {pdf_path}", file=sys.stderr)
        return 1

    try:
        if args.debug_page:
            for line in debug_page_from_path(pdf_path, args.debug_page):
                print(line)
            return 0

        records = extract_records_from_path(pdf_path, args.codes)
        write_xlsx(Path(args.xlsx), records)
        print(f"{len(records)} linhas exportadas para {args.xlsx}")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
