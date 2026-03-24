from pathlib import Path

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from app.config import settings


class NLLBTranslator:
    """Обгортка над NLLB-моделлю для перекладу тексту."""

    def __init__(self) -> None:
        """Ініціалізує токенайзер і модель перекладу з локальним кешем."""
        cache_dir = Path(settings.model_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        self._tokenizer = AutoTokenizer.from_pretrained(
            settings.model_name,
            cache_dir=str(cache_dir),
            local_files_only=settings.transformers_offline,
        )
        self._model = AutoModelForSeq2SeqLM.from_pretrained(
            settings.model_name,
            cache_dir=str(cache_dir),
            local_files_only=settings.transformers_offline,
        )

    def translate(self, text: str, target_language: str) -> str:
        """Перекладає арабський текст у вказану цільову мову NLLB.

        Args:
            text: Вхідний текст для перекладу.
            target_language: Код цільової мови NLLB (наприклад, `rus_Cyrl` або `ukr_Cyrl`).

        Returns:
            Перекладений текст.
        """
        self._tokenizer.src_lang = settings.src_lang
        inputs = self._tokenizer(text, return_tensors="pt")
        generation_kwargs: dict[str, int] = {
            "forced_bos_token_id": self._tokenizer.convert_tokens_to_ids(target_language),
        }
        if settings.max_length > 0:
            generation_kwargs["max_length"] = settings.max_length
        translated_tokens = self._model.generate(**inputs, **generation_kwargs)
        return self._tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
