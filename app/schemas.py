from typing import Literal

from pydantic import BaseModel, Field

from app.config import TEXT_MIN_LENGTH, settings

TranslateFormat = Literal["text", "html"]


class TranslateRequest(BaseModel):
    """Запит на переклад одного текстового фрагмента."""

    text: str = Field(
        min_length=TEXT_MIN_LENGTH,
        max_length=settings.request_text_max_length,
        description="Вхідний текст для перекладу.",
        examples=["مرحبا كيف حالك"],
    )
    target_language: Literal["ru", "uk"] | None = Field(
        default=None,
        description="Цільова мова перекладу: `ru` (російська) або `uk` (українська). Якщо не передано, використовується NLLB_DEFAULT_TARGET_LANGUAGE.",
        examples=["ru", "uk"],
    )
    source_language: str | None = Field(
        default=None,
        description=(
            "Alias вхідної мови або NLLB-код (наприклад, `arb_Arab`, `eng_Latn`). "
            "Передайте auto або не передавайте поле — мова визначиться автоматично. "
            "Підтримуються всі 200 мов NLLB-200, а також короткі alias-и: "
            "`ar`, `en`, `pl`, `sk`, `hu`, `ro`, `md`, `be`, `ru`."
        ),
        examples=["auto", "ar", "arb_Arab", "pol_Latn"],
    )
    format: TranslateFormat = Field(
        default="text",
        description=(
            "Формат вхідного тексту: `text` (звичайний, за замовчуванням) або `html` "
            "(HTML-розмітка — перекладаються лише текстові вузли, теги та атрибути зберігаються)."
        ),
        examples=["text", "html"],
    )


class TranslateResponse(BaseModel):
    """Успішна відповідь сервісу перекладу."""

    translation: str = Field(description="Результат перекладу цільовою мовою.")
    source_language: str = Field(description="Код вихідної мови у форматі NLLB.")
    target_language: str = Field(description="Код цільової мови у форматі NLLB.")
    model_name: str = Field(description="Назва моделі перекладу.")


class ErrorResponse(BaseModel):
    """Стандартна помилка API."""

    detail: str = Field(description="Опис причини помилки.")


class LanguagesResponse(BaseModel):
    """Список підтримуваних source/target мов сервісу."""

    source_languages: dict[str, str] = Field(description="Мапа alias -> NLLB код для вхідних мов.")
    target_languages: dict[str, str] = Field(description="Мапа alias -> NLLB код для цільових мов.")
    default_target_language: str = Field(description="Alias цільової мови за замовчуванням.")
