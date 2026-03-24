from typing import Literal

from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    """Запит на переклад одного текстового фрагмента."""

    text: str = Field(
        min_length=1,
        max_length=10_000,
        description="Вхідний текст арабською мовою (arb_Arab).",
        examples=["مرحبا كيف حالك"],
    )
    target_language: Literal["ru", "uk"] | None = Field(
        default=None,
        description="Цільова мова перекладу: `ru` (російська) або `uk` (українська). Якщо не передано, використовується NLLB_DEFAULT_TARGET_LANGUAGE.",
        examples=["ru", "uk"],
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
