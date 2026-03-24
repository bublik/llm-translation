from typing import Literal

from pydantic import BaseModel, Field

from app.config import TEXT_MIN_LENGTH, settings

SourceLanguageAlias = Literal["ar", "pl", "sk", "hu", "ro", "md", "be", "ru"]


class TranslateRequest(BaseModel):
    """Запит на переклад одного текстового фрагмента."""

    text: str = Field(
        min_length=TEXT_MIN_LENGTH,
        max_length=settings.request_text_max_length,
        description="Вхідний текст для перекладу (наприклад, арабською `arb_Arab`).",
        examples=["مرحبا كيف حالك"],
    )
    target_language: Literal["ru", "uk"] | None = Field(
        default=None,
        description="Цільова мова перекладу: `ru` (російська) або `uk` (українська). Якщо не передано, використовується NLLB_DEFAULT_TARGET_LANGUAGE.",
        examples=["ru", "uk"],
    )
    source_language: SourceLanguageAlias | None = Field(
        default=None,
        description=(
            "Вхідна мова (alias): `ar`, `pl`, `sk`, `hu`, `ro`, `md`, `be`, `ru`. "
            "Якщо не передано, використовується `NLLB_SRC_LANG`."
        ),
        examples=["ar", "pl", "ro"],
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
