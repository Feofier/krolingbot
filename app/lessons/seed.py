import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Exercise, Language, Lesson

LANGS = [
    {"code": "en", "name": "Английский", "flag": "🇬🇧"},
    {"code": "es", "name": "Испанский", "flag": "🇪🇸"},
]

LEVELS = ["A1", "A2", "B1"]
LEVEL_TITLES = {
    "A1": ["Первые слова", "Семья и друзья", "Еда и напитки", "Дом", "Природа",
           "Действия", "Описания", "Цвета", "Числа", "Дни и время"],
    "A2": ["Покупки", "В ресторане", "Город", "Транспорт", "Работа",
           "Здоровье", "Путешествия", "Погода", "Хобби", "Свободное время"],
    "B1": ["Мнения", "Планы", "Отношения", "Новости", "Технологии",
           "Образование", "Культура", "Спорт", "Бизнес", "Общество"],
}
LEVEL_NAMES = {"A1": "Начальный", "A2": "Базовый", "B1": "Средний"}

# Слова: (слово, перевод)
WORDS = {
    "en": {
        "A1": [("cat", "кот"), ("dog", "собака"), ("house", "дом"), ("water", "вода"),
               ("apple", "яблоко"), ("book", "книга"), ("friend", "друг"), ("sun", "солнце"),
               ("tree", "дерево"), ("milk", "молоко"), ("bread", "хлеб"), ("school", "школа"),
               ("time", "время"), ("hand", "рука"), ("day", "день"), ("night", "ночь"),
               ("family", "семья"), ("city", "город"), ("river", "река"), ("music", "музыка"),
               ("run", "бежать"), ("eat", "есть"), ("drink", "пить"), ("sleep", "спать"),
               ("read", "читать"), ("write", "писать"), ("big", "большой"), ("small", "маленький"),
               ("good", "хороший"), ("new", "новый"), ("old", "старый"), ("happy", "счастливый"),
               ("red", "красный"), ("blue", "синий"), ("green", "зелёный"), ("white", "белый"),
               ("one", "один"), ("two", "два"), ("three", "три"), ("today", "сегодня"),
               ("tomorrow", "завтра"), ("morning", "утро"), ("evening", "вечер")],
        "A2": [("shop", "магазин"), ("price", "цена"), ("money", "деньги"), ("bill", "счёт"),
               ("waiter", "официант"), ("menu", "меню"), ("dish", "блюдо"), ("tasty", "вкусный"),
               ("street", "улица"), ("bus", "автобус"), ("train", "поезд"), ("ticket", "билет"),
               ("job", "работа"), ("boss", "начальник"), ("meeting", "встреча"), ("salary", "зарплата"),
               ("doctor", "врач"), ("medicine", "лекарство"), ("hotel", "отель"), ("luggage", "багаж"),
               ("weather", "погода"), ("rain", "дождь"), ("snow", "снег"), ("wind", "ветер"),
               ("hobby", "хобби"), ("game", "игра"), ("party", "вечеринка"), ("gift", "подарок"),
               ("neighbour", "сосед"), ("weekend", "выходные"), ("holiday", "праздник"), ("market", "рынок"),
               ("bank", "банк"), ("post", "почта"), ("map", "карта"), ("bridge", "мост"),
               ("square", "площадь"), ("museum", "музей"), ("cinema", "кинотеатр"), ("stadium", "стадион")],
        "B1": [("opinion", "мнение"), ("reason", "причина"), ("decision", "решение"), ("choice", "выбор"),
               ("plan", "план"), ("goal", "цель"), ("future", "будущее"), ("hope", "надежда"),
               ("relationship", "отношения"), ("trust", "доверие"), ("argue", "спорить"), ("agree", "соглашаться"),
               ("news", "новости"), ("event", "событие"), ("report", "отчёт"), ("source", "источник"),
               ("device", "устройство"), ("screen", "экран"), ("data", "данные"), ("network", "сеть"),
               ("degree", "степень"), ("skill", "навык"), ("knowledge", "знания"), ("exam", "экзамен"),
               ("culture", "культура"), ("tradition", "традиция"), ("art", "искусство"), ("performance", "спектакль"),
               ("competition", "соревнование"), ("training", "тренировка"), ("coach", "тренер"), ("victory", "победа"),
               ("customer", "клиент"), ("contract", "контракт"), ("profit", "прибыль"), ("deadline", "срок"),
               ("society", "общество"), ("law", "закон"), ("rights", "права"), ("volunteer", "волонтёр")],
    },
    "es": {
        "A1": [("gato", "кот"), ("perro", "собака"), ("casa", "дом"), ("agua", "вода"),
               ("manzana", "яблоко"), ("libro", "книга"), ("amigo", "друг"), ("sol", "солнце"),
               ("árbol", "дерево"), ("leche", "молоко"), ("pan", "хлеб"), ("escuela", "школа"),
               ("tiempo", "время"), ("mano", "рука"), ("día", "день"), ("noche", "ночь"),
               ("familia", "семья"), ("ciudad", "город"), ("río", "река"), ("música", "музыка"),
               ("correr", "бежать"), ("comer", "есть"), ("beber", "пить"), ("dormir", "спать"),
               ("leer", "читать"), ("escribir", "писать"), ("grande", "большой"), ("pequeño", "маленький"),
               ("bueno", "хороший"), ("nuevo", "новый"), ("viejo", "старый"), ("feliz", "счастливый"),
               ("rojo", "красный"), ("azul", "синий"), ("verde", "зелёный"), ("blanco", "белый"),
               ("uno", "один"), ("dos", "два"), ("tres", "три"), ("hoy", "сегодня"),
               ("mañana", "завтра"), ("mañana_q", "утро"), ("tarde", "вечер")],
        "A2": [("tienda", "магазин"), ("precio", "цена"), ("dinero", "деньги"), ("cuenta", "счёт"),
               ("camarero", "официант"), ("menú", "меню"), ("plato", "блюдо"), ("rico", "вкусный"),
               ("calle", "улица"), ("autobús", "автобус"), ("tren", "поезд"), ("billete", "билет"),
               ("trabajo", "работа"), ("jefe", "начальник"), ("reunión", "встреча"), ("sueldo", "зарплата"),
               ("médico", "врач"), ("medicina", "лекарство"), ("hotel", "отель"), ("equipaje", "багаж"),
               ("tiempo_q", "погода"), ("lluvia", "дождь"), ("nieve", "снег"), ("viento", "ветер"),
               ("pasatiempo", "хобби"), ("juego", "игра"), ("fiesta", "вечеринка"), ("regalo", "подарок"),
               ("vecino", "сосед"), ("finde", "выходные"), ("fiesta_q", "праздник"), ("mercado", "рынок"),
               ("banco", "банк"), ("correo", "почта"), ("mapa", "карта"), ("puente", "мост"),
               ("plaza", "площадь"), ("museo", "музей"), ("cine", "кинотеатр"), ("estadio", "стадион")],
        "B1": [("opinión", "мнение"), ("razón", "причина"), ("decisión", "решение"), ("elección", "выбор"),
               ("plan", "план"), ("meta", "цель"), ("futuro", "будущее"), ("esperanza", "надежда"),
               ("relación", "отношения"), ("confianza", "доверие"), ("discutir", "спорить"), ("aceptar", "соглашаться"),
               ("noticias", "новости"), ("evento", "событие"), ("informe", "отчёт"), ("fuente", "источник"),
               ("dispositivo", "устройство"), ("pantalla", "экран"), ("datos", "данные"), ("red", "сеть"),
               ("título", "степень"), ("habilidad", "навык"), ("conocimiento", "знания"), ("examen", "экзамен"),
               ("cultura", "культура"), ("tradición", "традиция"), ("arte", "искусство"), ("función", "спектакль"),
               ("competición", "соревнование"), ("entrenamiento", "тренировка"), ("entrenador", "тренер"), ("victoria", "победа"),
               ("cliente", "клиент"), ("contrato", "контракт"), ("beneficio", "прибыль"), ("plazo", "срок"),
               ("sociedad", "общество"), ("ley", "закон"), ("derechos", "права"), ("voluntario", "волонтёр")],
    },
}

# (русский источник, правильный ответ)
SENTENCES = {
    "en": {
        "A1": [("Я пью воду", "I drink water"), ("Кот ест хлеб", "The cat eats bread"),
               ("Она читает книгу", "She reads a book"), ("Мы бежим домой", "We run home"),
               ("Солнце большое", "The sun is big"), ("Друг пишет письмо", "A friend writes a letter"),
               ("Я вижу собаку", "I see a dog"), ("Дети пьют молоко", "Children drink milk")],
        "A2": [("Я покупаю билет", "I buy a ticket"), ("Официант приносит меню", "The waiter brings the menu"),
               ("Поезд идёт в город", "The train goes to the city"), ("Врач работает в больнице", "The doctor works in a hospital"),
               ("Дождь идёт всю неделю", "It rains all week"), ("Мы едем на выходные", "We travel on the weekend"),
               ("Сосед играет в игру", "The neighbour plays a game"), ("Она платит по счёту", "She pays the bill")],
        "B1": [("Я думаю что это правильно", "I think that it is right"), ("Он принял важное решение", "He made an important decision"),
               ("Мы обсуждаем новости", "We discuss the news"), ("Она доверяет своему тренеру", "She trusts her coach"),
               ("Компания получает прибыль", "The company makes a profit"), ("Они планируют путешествие", "They plan a trip"),
               ("Студент сдаёт экзамен", "The student takes an exam"), ("Закон защищает права", "The law protects rights")],
    },
    "es": {
        "A1": [("Я пью воду", "Yo bebo agua"), ("Кот ест хлеб", "El gato come pan"),
               ("Она читает книгу", "Ella lee un libro"), ("Мы бежим домой", "Nosotros corremos a casa"),
               ("Солнце большое", "El sol es grande"), ("Друг пишет письмо", "Un amigo escribe una carta"),
               ("Я вижу собаку", "Yo veo un perro"), ("Дети пьют молоко", "Los niños beben leche")],
        "A2": [("Я покупаю билет", "Yo compro un billete"), ("Официант приносит меню", "El camarero trae el menú"),
               ("Поезд идёт в город", "El tren va a la ciudad"), ("Врач работает в больнице", "El médico trabaja en un hospital"),
               ("Дождь идёт всю неделю", "Llueve toda la semana"), ("Мы едем на выходные", "Viajamos el fin de semana"),
               ("Сосед играет в игру", "El vecino juega un juego"), ("Она платит по счёту", "Ella paga la cuenta")],
        "B1": [("Я думаю что это правильно", "Pienso que es correcto"), ("Он принял важное решение", "Él tomó una decisión importante"),
               ("Мы обсуждаем новости", "Discutimos las noticias"), ("Она доверяет своему тренеру", "Ella confía en su entrenador"),
               ("Компания получает прибыль", "La empresa obtiene beneficios"), ("Они планируют путешествие", "Ellos planean un viaje"),
               ("Студент сдаёт экзамен", "El estudiante hace un examen"), ("Закон защищает права", "La ley protege los derechos")],
    },
}

DECOYS = {
    "en": ["blue", "night", "small", "music", "they", "old", "hand", "two", "quickly", "never"],
    "es": ["azul", "noche", "pequeño", "música", "ellos", "viejo", "mano", "dos", "rápido", "nunca"],
}


def make_exercises(words, sentences, rng, lang_code):
    exercises = []
    n = min(len(words), 10)
    translations = dict(words)
    for i in range(n):
        word, translation = words[i]
        distractors = rng.sample([w for w, _ in words if w != word], 3)
        exercises.append(("choice", f"Как переводится «{word}»?",
                          {"options": [translation] + [translations[d] for d in distractors],
                           "correct": translation}))
    words2 = words[10:20] if len(words) > 10 else words[:10]
    for word, _t in words2[:5]:
        distractors = rng.sample([w for w, _ in words if w != word], 3)
        exercises.append(("gap", f"Вставь слово: I see a ___ .",
                          {"sentence": "I see a ___ .", "options": distractors + [word],
                           "correct": word}))
    pairs = rng.sample(words, min(5, len(words)))
    exercises.append(("pairs", "Соедини пары:",
                      {"pairs": [[w, t] for w, t in pairs]}))
    for src, correct in sentences:
        pool = correct.split() + rng.sample(DECOYS[lang_code], 3)
        exercises.append(("sentence", f"Переведи: «{src}»",
                          {"bank": pool, "correct": correct}))
    return exercises


async def seed_if_empty(session: AsyncSession) -> None:
    count = (await session.execute(select(func.count(Language.id)))).scalar_one()
    if count:
        return

    rng = random.Random(42)
    for lang in LANGS:
        language = Language(code=lang["code"], name=lang["name"], flag=lang["flag"])
        session.add(language)
        await session.flush()
        for level in LEVELS:
            words = WORDS[lang["code"]][level]
            sentences = SENTENCES[lang["code"]][level]
            for num, title in enumerate(LEVEL_TITLES[level], start=1):
                chunk = words[(num - 1) * 4:(num - 1) * 4 + 10] or words[:10]
                sents = [sentences[(num - 1) * 2 % len(sentences)],
                         sentences[((num - 1) * 2 + 1) % len(sentences)]]
                lesson = Lesson(language_id=language.id, level=level, number=num,
                                title=f"{title}")
                session.add(lesson)
                await session.flush()
                for etype, prompt, payload in make_exercises(chunk, sents, rng, lang["code"]):
                    session.add(Exercise(lesson_id=lesson.id, type=etype,
                                         prompt=prompt, payload=payload))
    await session.commit()
