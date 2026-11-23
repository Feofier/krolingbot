"""Мультиязычный фильтр нецензурной лексики (компактный список самых частых)."""

WORDS = {
    "ru": ["хуй", "пизд", "еба", "бляд", "сука", "мудил", "пидор", "шлюх", "залуп", "долбоёб", "уёбищ"],
    "en": ["fuck", "shit", "bitch", "cunt", "nigger", "whore", "slut", "dick", "pussy"],
    "es": ["puta", "mierda", "joder", "cabrón", "pendejo", "polla"],
    "de": ["fick", "scheiß", "hure", "schwanz", "fotze", "arsch"],
    "fr": ["putain", "merde", "salope", "enculé", "bite", "chatte"],
    "it": ["cazzo", "puttana", "merda", "fica", "stronzo"],
    "pt": ["puta", "merda", "caralho", "buceta", "viado"],
    "tr": ["amcık", "yarak", "orospu", "sik", "göt"],
    "pl": ["kurwa", "chuj", "pizda", "skurwysyn", "dziwka"],
    "uk": ["хуй", "пізд", "єбá", "блядь", "сука", "шлюха", "долбоєб"],
    "ja": ["ばか", "くそ", "ちくしょう"],
    "zh": ["操你", "傻逼", "婊子", "鸡巴"],
}


def is_clean(text):
    low = text.lower()
    for words in WORDS.values():
        for w in words:
            if w in low:
                return False
    return True
