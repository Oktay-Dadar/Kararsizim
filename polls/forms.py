from django import forms
from django.core.exceptions import ValidationError

MIN_OPTIONS = 2
MAX_OPTIONS = 5
OPTION_MAX_LENGTH = 80


class OptionListWidget(forms.Widget):
    """Reads every value posted under the same name (name="options")."""

    def value_from_datadict(self, data, files, name):
        if hasattr(data, "getlist"):
            return data.getlist(name)
        value = data.get(name, [])
        return value if isinstance(value, list) else [value]


class OptionListField(forms.Field):
    widget = OptionListWidget

    def clean(self, value):
        texts = [str(item).strip() for item in (value or [])]
        texts = [text for text in texts if text]
        if len(texts) < MIN_OPTIONS:
            raise ValidationError("En az 2 seçenek gerekli.", code="too_few")
        if len(texts) > MAX_OPTIONS:
            raise ValidationError("En fazla 5 seçenek ekleyebilirsin.", code="too_many")
        if any(len(text) > OPTION_MAX_LENGTH for text in texts):
            raise ValidationError("Bir seçenek en fazla 80 karakter olabilir.", code="too_long")
        seen = set()
        for text in texts:
            key = text.casefold()
            if key in seen:
                raise ValidationError(f"“{text}” seçeneğini iki kez yazdın.", code="duplicate")
            seen.add(key)
        return texts


class PollForm(forms.Form):
    question = forms.CharField(
        label="Soru",
        min_length=10,
        max_length=140,
        help_text="10–140 karakter.",
        error_messages={
            "required": "Bir soru yaz.",
            "min_length": "Soru en az 10 karakter olmalı.",
            "max_length": "Soru en fazla 140 karakter olabilir.",
        },
    )
    description = forms.CharField(
        label="Açıklama (isteğe bağlı)",
        max_length=280,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="En fazla 280 karakter.",
        error_messages={"max_length": "Açıklama en fazla 280 karakter olabilir."},
    )
    options = OptionListField(label="Seçenekler")

    def option_values(self):
        """Five input slots, pre-filled with whatever was posted."""
        posted = (self["options"].value() or []) if self.is_bound else []
        posted = [str(item) for item in posted if str(item).strip()][:MAX_OPTIONS]
        return posted + [""] * (MAX_OPTIONS - len(posted))
