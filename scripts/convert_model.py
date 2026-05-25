#!/usr/bin/env python3
"""Конвертує HuggingFace NLLB-200 модель у формат CTranslate2 з INT8 квантизацією.

Потребує: pip install -r requirements-convert.txt

Приклад використання:
    python scripts/convert_model.py
    python scripts/convert_model.py --model facebook/nllb-200-distilled-1.3B --output /app/storage/ct2-nllb-1.3b-int8
    python scripts/convert_model.py --quantization int8_float16 --device cuda
"""
import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Конвертація NLLB HuggingFace → CTranslate2")
    parser.add_argument(
        "--model",
        default="facebook/nllb-200-distilled-1.3B",
        help="HuggingFace model ID або локальний шлях (default: facebook/nllb-200-distilled-1.3B)",
    )
    parser.add_argument(
        "--output",
        default="/app/storage/ct2-nllb-1.3b-int8",
        help="Директорія для збереження CT2 моделі (default: /app/storage/ct2-nllb-1.3b-int8)",
    )
    parser.add_argument(
        "--quantization",
        default="int8",
        choices=["int8", "int8_float16", "int16", "float16", "float32"],
        help="Тип квантизації (default: int8)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda"],
        help="Пристрій для конвертації (default: cpu)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Перезаписати існуючу директорію output",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from ctranslate2.converters import OpusMTConverter  # noqa: F401 — перевірка наявності ct2
        import ctranslate2.converters
    except ImportError:
        print("ERROR: ctranslate2 не встановлено. Запустіть: pip install -r requirements-convert.txt", file=sys.stderr)
        sys.exit(1)

    try:
        import torch  # noqa: F401 — потрібен для завантаження HF моделі
    except ImportError:
        print("ERROR: torch не встановлено. Запустіть: pip install -r requirements-convert.txt", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        print(f"Директорія '{output_path}' вже існує. Додайте --force для перезапису.")
        sys.exit(0)

    print(f"Модель:       {args.model}")
    print(f"Output:       {output_path}")
    print(f"Квантизація:  {args.quantization}")
    print(f"Пристрій:     {args.device}")
    print()

    converter = ctranslate2.converters.TransformersConverter(
        args.model,
        low_cpu_mem_usage=True,
    )
    output_path.mkdir(parents=True, exist_ok=True)
    converter.convert(
        str(output_path),
        quantization=args.quantization,
        force=args.force,
    )

    print(f"\nГотово! CT2 модель збережено: {output_path}")
    print("Встановіть NLLB_CT2_MODEL_DIR у .env або передайте через env при запуску сервісу.")


if __name__ == "__main__":
    main()
