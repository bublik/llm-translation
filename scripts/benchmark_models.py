#!/usr/bin/env python3
"""Порівняння якості перекладу між двома CT2-моделями NLLB.

Запуск:
    python scripts/benchmark_models.py \
        --model-a /home/grumbler/data/storage/ct2-nllb-1.3b-int8 \
        --model-b /home/grumbler/data/storage/ct2-nllb-1.3b-nondistilled-int8 \
        --tokenizer-a facebook/nllb-200-distilled-1.3B \
        --tokenizer-b facebook/nllb-200-1.3B

Або порівняти одну модель із собою (для smoke-test):
    python scripts/benchmark_models.py \
        --model-a /home/grumbler/data/storage/ct2-nllb-1.3b-int8 \
        --tokenizer-a facebook/nllb-200-distilled-1.3B
"""
import argparse
import time
from dataclasses import dataclass
from pathlib import Path

# Тестові пари: (текст, src_lang, tgt_lang, мітка)
# Підібрані під реальний виробничий домен (ru→uk + ar→uk/ru)
TEST_CASES = [
    # ── Військові радіоперехоплення (основний домен) ──────────────────────────
    ("51й Печора прием.", "rus_Cyrl", "ukr_Cyrl", "military/callsign-short"),
    ("Снежок, Снежок Печора. Короче, крепимся, ждём команды.", "rus_Cyrl", "ukr_Cyrl", "military/order"),
    ("56-й, добро на форточку.", "rus_Cyrl", "ukr_Cyrl", "military/confirm"),
    ("Убыток 484 для вас имею. 484 принял до обртаного. Спасибо.", "rus_Cyrl", "ukr_Cyrl", "military/report"),
    ("Все так же крепимся, ждём команды. Конец связи.", "rus_Cyrl", "ukr_Cyrl", "military/status"),
    ("Движение наблюдается в квадрате восемь. Подтвердите получение.", "rus_Cyrl", "ukr_Cyrl", "military/intel"),
    ("Первый, первый, я второй. Как слышно? Приём.", "rus_Cyrl", "ukr_Cyrl", "military/radio-check"),
    ("Отработали по цели, возвращаемся на базу.", "rus_Cyrl", "ukr_Cyrl", "military/debrief"),
    # ── Загальна мова Ru→Uk ───────────────────────────────────────────────────
    ("Добрый день, как дела?", "rus_Cyrl", "ukr_Cyrl", "general/greeting"),
    ("Ситуация на фронте остаётся напряжённой.", "rus_Cyrl", "ukr_Cyrl", "general/news"),
    ("Необходимо провести техническое обслуживание транспортного средства.", "rus_Cyrl", "ukr_Cyrl", "general/long"),
    # ── Арабська → Українська ─────────────────────────────────────────────────
    ("مرحبا، كيف حالك؟", "arb_Arab", "ukr_Cyrl", "arabic/greeting"),
    ("الوضع في المنطقة لا يزال متوتراً.", "arb_Arab", "ukr_Cyrl", "arabic/news"),
    # ── Арабська → Російська ──────────────────────────────────────────────────
    ("تم الانتهاء من المهمة بنجاح.", "arb_Arab", "rus_Cyrl", "arabic/mission-ru"),
]


@dataclass
class ModelRunner:
    model_dir: str
    tokenizer_name: str
    label: str
    _ct2: object = None
    _tok: object = None

    def load(self) -> None:
        import ctranslate2
        from transformers import AutoTokenizer

        print(f"  Завантаження CT2 [{self.label}]: {self.model_dir}")
        self._ct2 = ctranslate2.Translator(self.model_dir, device="cpu", inter_threads=1)
        print(f"  Завантаження токенайзера [{self.label}]: {self.tokenizer_name}")
        self._tok = AutoTokenizer.from_pretrained(self.tokenizer_name)
        print(f"  [{self.label}] готовий\n")

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> tuple[str, float]:
        self._tok.src_lang = src_lang
        encoded = self._tok(text)
        tokens = self._tok.convert_ids_to_tokens(encoded["input_ids"])

        t0 = time.perf_counter()
        results = self._ct2.translate_batch(
            [tokens],
            target_prefix=[[tgt_lang]],
            max_decoding_length=256,
        )
        elapsed = time.perf_counter() - t0

        output_tokens = results[0].hypotheses[0][1:]
        ids = self._tok.convert_tokens_to_ids(output_tokens)
        translation = self._tok.decode(ids, skip_special_tokens=True)
        return translation, elapsed


def _wrap(text: str, width: int = 48) -> list[str]:
    """Переносить текст по ширині для форматування таблиці."""
    words = text.split()
    lines, current = [], ""
    for w in words:
        if len(current) + len(w) + 1 <= width:
            current = (current + " " + w).lstrip()
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]


def run_benchmark(runner_a: ModelRunner, runner_b: ModelRunner | None) -> None:
    col = 50
    sep = "─" * (col * (3 if runner_b else 2) + (6 if runner_b else 3))

    header_a = f"[A] {runner_a.label}"
    header_b = f"[B] {runner_b.label}" if runner_b else ""

    total_a = total_b = 0.0
    count = 0

    for text, src, tgt, label in TEST_CASES:
        trans_a, t_a = runner_a.translate(text, src, tgt)
        total_a += t_a
        count += 1

        trans_b, t_b = (None, None)
        if runner_b:
            trans_b, t_b = runner_b.translate(text, src, tgt)
            total_b += t_b

        print(f"\n{'━' * 100}")
        print(f"  [{label}]  {src} → {tgt}")
        print(f"  Вхід: {text}")
        print(sep)

        src_lines  = _wrap(f"SRC: {text}", col)
        a_lines    = _wrap(f"[A] {trans_a} ({t_a*1000:.0f}ms)", col)
        b_lines    = _wrap(f"[B] {trans_b} ({t_b*1000:.0f}ms)", col) if runner_b else []

        max_rows = max(len(src_lines), len(a_lines), len(b_lines) if b_lines else 0)
        for i in range(max_rows):
            s = src_lines[i] if i < len(src_lines) else ""
            a = a_lines[i] if i < len(a_lines) else ""
            if runner_b:
                b = b_lines[i] if i < len(b_lines) else ""
                print(f"  {s:<{col}}  {a:<{col}}  {b:<{col}}")
            else:
                print(f"  {s:<{col}}  {a:<{col}}")

    print(f"\n{'━' * 100}")
    print(f"  Latency (avg):  [A] {total_a/count*1000:.0f}ms", end="")
    if runner_b:
        print(f"   |   [B] {total_b/count*1000:.0f}ms", end="")
    print("\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Порівняння двох CT2-моделей NLLB")
    p.add_argument("--model-a", required=True, help="Директорія CT2-моделі A (поточна)")
    p.add_argument("--model-b", help="Директорія CT2-моделі B (кандидат, опціонально)")
    p.add_argument(
        "--tokenizer-a",
        default="facebook/nllb-200-distilled-1.3B",
        help="HuggingFace tokenizer для моделі A",
    )
    p.add_argument(
        "--tokenizer-b",
        help="HuggingFace tokenizer для моделі B (якщо інший)",
    )
    p.add_argument("--label-a", default="distilled-1.3B", help="Мітка моделі A")
    p.add_argument("--label-b", default="candidate", help="Мітка моделі B")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not Path(args.model_a).exists():
        print(f"ERROR: model-a не знайдено: {args.model_a}")
        raise SystemExit(1)

    if args.model_b and not Path(args.model_b).exists():
        print(f"ERROR: model-b не знайдено: {args.model_b}")
        raise SystemExit(1)

    print("=== NLLB Model Benchmark ===\n")

    runner_a = ModelRunner(
        model_dir=args.model_a,
        tokenizer_name=args.tokenizer_a,
        label=args.label_a,
    )
    runner_a.load()

    runner_b = None
    if args.model_b:
        tok_b = args.tokenizer_b or args.tokenizer_a
        runner_b = ModelRunner(
            model_dir=args.model_b,
            tokenizer_name=tok_b,
            label=args.label_b,
        )
        runner_b.load()

    run_benchmark(runner_a, runner_b)


if __name__ == "__main__":
    main()