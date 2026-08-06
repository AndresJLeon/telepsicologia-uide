import pandas as pd
from transformers import MarianMTModel, MarianTokenizer
from typing import List, Dict, Optional
import re


class MarianTranslator:
    """Translation pipeline using MarianMT from Hugging Face."""

    def __init__(self):
        self.models = {}
        self.tokenizers = {}
        # Models that translate TO Spanish (source -> es)
        self._lang_pairs = {
            "en-es": "Helsinki-NLP/opus-mt-en-es",
            "fr-es": "Helsinki-NLP/opus-mt-fr-es",
            "de-es": "Helsinki-NLP/opus-mt-de-es",
            "it-es": "Helsinki-NLP/opus-mt-it-es",
            "ja-es": "Helsinki-NLP/opus-mt-ja-es",
            "ko-es": "Helsinki-NLP/opus-mt-ko-es",
            "ru-es": "Helsinki-NLP/opus-mt-ru-es",
            "ar-es": "Helsinki-NLP/opus-mt-ar-es",
            # Models that translate FROM Spanish (es -> target)
            "es-en": "Helsinki-NLP/opus-mt-es-en",
            "es-fr": "Helsinki-NLP/opus-mt-es-fr",
            "es-de": "Helsinki-NLP/opus-mt-es-de",
            "es-it": "Helsinki-NLP/opus-mt-es-it",
        }

    def _load_model(self, lang_pair: str):
        """Lazy-load a translation model."""
        if lang_pair in self.models:
            return

        if lang_pair not in self._lang_pairs:
            raise ValueError(
                f"Par de idiomas no soportado: {lang_pair}. "
                f"Disponibles: {list(self._lang_pairs.keys())}"
            )

        model_name = self._lang_pairs[lang_pair]
        self.tokenizers[lang_pair] = MarianTokenizer.from_pretrained(model_name)
        self.models[lang_pair] = MarianMTModel.from_pretrained(model_name)

    def translate_text(self, text: str, source_lang: str = "en", target_lang: str = "es") -> str:
        """Translate a single text string."""
        if not text or not isinstance(text, str):
            return text

        text = text.strip()
        if not text:
            return text

        if source_lang == target_lang:
            return text

        lang_pair = f"{source_lang}-{target_lang}"
        self._load_model(lang_pair)

        tokenizer = self.tokenizers[lang_pair]
        model = self.models[lang_pair]

        chunks = self._split_text(text, max_length=450)
        translated_chunks = []

        for chunk in chunks:
            encoded = tokenizer(chunk, return_tensors="pt", padding=True, truncation=True, max_length=512)
            translated = model.generate(**encoded)
            decoded = tokenizer.decode(translated[0], skip_special_tokens=True)
            translated_chunks.append(decoded)

        return " ".join(translated_chunks)

    def translate_batch(self, texts: List[str], source_lang: str = "en", target_lang: str = "es", batch_size: int = 8) -> List[str]:
        """Translate a list of texts in batches."""
        if not texts:
            return []

        lang_pair = f"{source_lang}-{target_lang}"
        self._load_model(lang_pair)

        tokenizer = self.tokenizers[lang_pair]
        model = self.models[lang_pair]

        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch = [t.strip() if isinstance(t, str) else "" for t in batch]

            encoded = tokenizer(
                batch, return_tensors="pt", padding=True,
                truncation=True, max_length=512
            )
            translated = model.generate(**encoded)
            decoded = tokenizer.batch_decode(translated, skip_special_tokens=True)
            results.extend(decoded)

        return results

    def translate_dataframe(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        source_lang: str = "en",
        target_lang: str = "es",
    ) -> pd.DataFrame:
        """Translate specified columns in a DataFrame."""
        df_translated = df.copy()

        if columns is None:
            columns = [col for col in df.columns if not pd.api.types.is_numeric_dtype(df[col])]

        for col in columns:
            if col in df.columns:
                non_null_mask = df[col].notna()
                texts_to_translate = df.loc[non_null_mask, col].astype(str).tolist()
                translated = self.translate_batch(texts_to_translate, source_lang, target_lang)
                df_translated.loc[non_null_mask, col] = translated

        return df_translated

    def _split_text(self, text: str, max_length: int = 450) -> List[str]:
        """Split long text into chunks for translation."""
        if len(text) <= max_length:
            return [text]

        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_length:
                current_chunk += (" " if current_chunk else "") + sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks if chunks else [text]

    def get_supported_languages(self) -> Dict[str, str]:
        """Return supported language pairs."""
        return {
            "en": "Ingles",
            "fr": "Frances",
            "de": "Aleman",
            "it": "Italiano",
            "ja": "Japones",
            "ko": "Coreano",
            "ru": "Ruso",
            "ar": "Arabe",
            "es": "Espanol",
        }

    def get_source_languages(self) -> Dict[str, str]:
        """Return languages that can be translated FROM."""
        return {
            "en": "Ingles",
            "fr": "Frances",
            "de": "Aleman",
            "it": "Italiano",
            "ja": "Japones",
            "ko": "Coreano",
            "ru": "Ruso",
            "ar": "Arabe",
        }

    def get_target_languages(self) -> Dict[str, str]:
        """Return languages that can be translated TO."""
        return {
            "es": "Espanol",
            "en": "Ingles",
            "fr": "Frances",
            "de": "Aleman",
            "it": "Italiano",
        }
