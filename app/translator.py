from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from app.config import settings


class NLLBTranslator:
    """Обгортка над NLLB-моделлю для перекладу тексту."""

    def __init__(self) -> None:
        """Ініціалізує токенайзер і модель перекладу."""
        self._tokenizer = AutoTokenizer.from_pretrained(settings.model_name)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(settings.model_name)

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
        translated_tokens = self._model.generate(
            **inputs,
            forced_bos_token_id=self._tokenizer.convert_tokens_to_ids(target_language),
            max_length=settings.max_length,
        )
        return self._tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
