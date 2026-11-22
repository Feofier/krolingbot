import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Exercise, Language, Lesson

LANGS = [
    {"code": "en", "name": "Английский", "flag": "🇬🇧"},
    {"code": "es", "name": "Испанский", "flag": "🇪🇸"},
]

LEVELS = ["A1", "A2", "B1", "B2", "C1"]
LEVEL_TITLES = {
    "A1": ["Первые слова", "Семья и друзья", "Еда и напитки", "Дом", "Природа",
           "Действия", "Описания", "Цвета", "Числа", "Дни и время"],
    "A2": ["Покупки", "В ресторане", "Город", "Транспорт", "Работа",
           "Здоровье", "Путешествия", "Погода", "Хобби", "Свободное время"],
    "B1": ["Мнения", "Планы", "Отношения", "Новости", "Технологии",
           "Образование", "Культура", "Спорт", "Бизнес", "Общество"],
    "B2": ["Наука", "Экология", "Экономика", "Политика", "Психология",
           "Медиа", "Искусство", "Инновации", "Глобализация", "Философия"],
    "C1": ["Абстракции", "Лингвистика", "Литература", "История", "Социология",
           "Этика", "Логика", "Эстетика", "Антропология", "Метафора"],
}
LEVEL_NAMES = {"A1": "Начальный", "A2": "Базовый", "B1": "Средний",
               "B2": "Продвинутый", "C1": "Владение"}

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
        "B2": [("research", "исследование"), ("hypothesis", "гипотеза"), ("evidence", "доказательство"),
               ("experiment", "эксперимент"), ("discovery", "открытие"),
               ("climate", "климат"), ("pollution", "загрязнение"), ("recycling", "переработка"),
               ("species", "вид"), ("extinction", "вымирание"),
               ("inflation", "инфляция"), ("investment", "инвестиции"), ("budget", "бюджет"),
               ("debt", "долг"), ("crisis", "кризис"),
               ("policy", "политика"), ("election", "выборы"), ("parliament", "парламент"),
               ("democracy", "демократия"), ("corruption", "коррупция"),
               ("behaviour", "поведение"), ("motivation", "мотивация"), ("anxiety", "тревога"),
               ("cognitive", "познавательный"), ("therapy", "терапия"),
               ("audience", "аудитория"), ("censorship", "цензура"), ("propaganda", "пропаганда"),
               ("headline", "заголовок"), ("broadcast", "трансляция"),
               ("masterpiece", "шедевр"), ("exhibition", "выставка"), ("genre", "жанр"),
               ("critic", "критик"), ("aesthetic", "эстетический")],
        "C1": [("ambiguity", "двусмысленность"), ("paradigm", "парадигма"), ("dichotomy", "дихотомия"),
               ("nuance", "нюанс"), ("rhetoric", "риторика"),
               ("syntax", "синтаксис"), ("semantics", "семантика"), ("etymology", "этимология"),
               ("phonetics", "фонетика"), ("dialect", "диалект"),
               ("narrative", "повествование"), ("allegory", "аллегория"), ("satire", "сатира"),
               ("tragedy", "трагедия"), ("irony", "ирония"),
               ("chronicle", "летопись"), ("heritage", "наследие"), ("revolution", "революция"),
               ("empire", "империя"), ("renaissance", "возрождение"),
               ("stratification", "стратификация"), ("institution", "институт"), ("marginalization", "маргинализация"),
               ("mobility", "мобильность"), ("cohesion", "сплочённость"),
               ("dilemma", "дилемма"), ("integrity", "честность"), ("accountability", "подотчётность"),
               ("solidarity", "солидарность"), ("tolerance", "терпимость"),
               ("inference", "вывод"), ("fallacy", "ошибка мышления"), ("axiom", "аксиома"),
               ("paradox", "парадокс"), ("scrutiny", "внимательное изучение"),
               ("metaphor", "метафора"), ("allegory_q", "иносказание"), ("juxtaposition", "сопоставление"),
               ("alienation", "отчуждение"), ("epiphany", "озарение")],
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
        "B2": [("investigación", "исследование"), ("hipótesis", "гипотеза"), ("evidencia", "доказательство"),
               ("experimento", "эксперимент"), ("descubrimiento", "открытие"),
               ("clima", "климат"), ("contaminación", "загрязнение"), ("reciclaje", "переработка"),
               ("especie", "вид"), ("extinción", "вымирание"),
               ("inflación", "инфляция"), ("inversión", "инвестиции"), ("presupuesto", "бюджет"),
               ("deuda", "долг"), ("crisis", "кризис"),
               ("política", "политика"), ("elecciones", "выборы"), ("parlamento", "парламент"),
               ("democracia", "демократия"), ("corrupción", "коррупция"),
               ("conducta", "поведение"), ("motivación", "мотивация"), ("ansiedad", "тревога"),
               ("cognitivo", "познавательный"), ("terapia", "терапия"),
               ("audiencia", "аудитория"), ("censura", "цензура"), ("propaganda", "пропаганда"),
               ("titular", "заголовок"), ("transmisión", "трансляция"),
               ("obra maestra", "шедевр"), ("exposición", "выставка"), ("género", "жанр"),
               ("crítico", "критик"), ("estético", "эстетический")],
        "C1": [("ambigüedad", "двусмысленность"), ("paradigma", "парадигма"), ("dicotomía", "дихотомия"),
               ("matiz", "нюанс"), ("retórica", "риторика"),
               ("sintaxis", "синтаксис"), ("semántica", "семантика"), ("etimología", "этимология"),
               ("fonética", "фонетика"), ("dialecto", "диалект"),
               ("narrativa", "повествование"), ("alegoría", "аллегория"), ("sátira", "сатира"),
               ("tragedia", "трагедия"), ("ironía", "ирония"),
               ("crónica", "летопись"), ("patrimonio", "наследие"), ("revolución", "революция"),
               ("imperio", "империя"), ("renacimiento", "возрождение"),
               ("estratificación", "стратификация"), ("institución", "институт"), ("marginación", "маргинализация"),
               ("movilidad", "мобильность"), ("cohesión", "сплочённость"),
               ("dilema", "дилемма"), ("integridad", "честность"), ("responsabilidad", "подотчётность"),
               ("solidaridad", "солидарность"), ("tolerancia", "терпимость"),
               ("inferencia", "вывод"), ("falacia", "ошибка мышления"), ("axioma", "аксиома"),
               ("paradoja", "парадокс"), ("escrutinio", "внимательное изучение"),
               ("metáfora", "метафора"), ("símbolo", "символ"), ("yuxtaposición", "сопоставление"),
               ("alienación", "отчуждение"), ("epifanía", "озарение")],
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
        "B2": [("Учёные проводят исследование", "Scientists conduct research"), ("Эксперимент подтвердил гипотезу", "The experiment confirmed the hypothesis"),
               ("Климат меняется быстро", "The climate is changing rapidly"), ("Переработка сокращает загрязнение", "Recycling reduces pollution"),
               ("Инфляция влияет на бюджет", "Inflation affects the budget"), ("Парламент принимает законы", "Parliament passes laws"),
               ("Терапия помогает при тревоге", "Therapy helps with anxiety"), ("Газета публикует заголовок", "The newspaper publishes a headline")],
        "C1": [("Смысл этого высказывания двусмысленен", "The meaning of this statement is ambiguous"),
               ("Ньюанс меняет всё", "The nuance changes everything"),
               ("Этимология слова восходит к латыни", "The etymology of the word traces back to Latin"),
               ("Аллегория скрывает глубокий смысл", "The allegory conceals a deep meaning"),
               ("Ирония осталась незамеченной", "The irony went unnoticed"),
               ("Наследие империи огромно", "The legacy of the empire is immense"),
               ("Это классический парадокс", "This is a classic paradox"),
               ("Метафора оживляет текст", "The metaphor brings the text to life")],
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
        "B2": [("Учёные проводят исследование", "Los científicos realizan una investigación"), ("Эксперимент подтвердил гипотезу", "El experimento confirmó la hipótesis"),
               ("Климат меняется быстро", "El clima cambia rápidamente"), ("Переработка сокращает загрязнение", "El reciclaje reduce la contaminación"),
               ("Инфляция влияет на бюджет", "La inflación afecta el presupuesto"), ("Парламент принимает законы", "El parlamento aprueba leyes"),
               ("Терапия помогает при тревоге", "La terapia ayuda con la ansiedad"), ("Газета публикует заголовок", "El periódico publica un titular")],
        "C1": [("Смысл этого высказывания двусмысленен", "El sentido de esta afirmación es ambiguo"),
               ("Ньюанс меняет всё", "El matiz lo cambia todo"),
               ("Этимология слова восходит к латыни", "La etimología de la palabra se remonta al latín"),
               ("Аллегория скрывает глубокий смысл", "La alegoría esconde un significado profundo"),
               ("Ирония осталась незамеченной", "La ironía pasó desapercibida"),
               ("Наследие империи огромно", "El legado del imperio es inmenso"),
               ("Это классический парадокс", "Esta es una paradoja clásica"),
               ("Метафора оживляет текст", "La metáfora da vida al texto")],
    },
}

DECOYS = {
    "en": ["blue", "night", "small", "music", "they", "old", "hand", "two", "quickly", "never"],
    "es": ["azul", "noche", "pequeño", "música", "ellos", "viejo", "mano", "dos", "rápido", "nunca"],
}


def make_exercises(words, sentences, rng, lang_code, lesson_num):
    exercises = []
    n = min(len(words), 10)
    translations = dict(words)
    word_strings = [w for w, _ in words]
    for i in range(n):
        word, translation = words[i]
        distractors = rng.sample([w for w, _ in words if w != word], 3)
        exercises.append(("choice", f"Как переводится «{word}»?",
                          {"options": [translation] + [translations[d] for d in distractors],
                           "correct": translation}))
    # gap: пропущенное слово в настоящем предложении — правильный ответ ровно один
    for gi in range(3):
        _src, correct_sentence = sentences[(lesson_num - 1 + gi) % len(sentences)]
        ws = correct_sentence.split()
        candidates = [i for i in range(1, len(ws) - 1) if len(ws[i]) > 2]
        if not candidates:
            continue
        idx = rng.choice(candidates)
        correct_word = ws[idx]
        distractors = rng.sample([w for w in word_strings if w != correct_word], 3)
        blank_sentence = " ".join(ws[:idx] + ["___"] + ws[idx + 1:])
        exercises.append(("gap", "Вставь пропущенное слово:",
                          {"sentence": blank_sentence,
                           "options": distractors + [correct_word],
                           "correct": correct_word}))
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
                start = (num - 1) * 4
                chunk = [words[(start + i) % len(words)] for i in range(10)]
                sents = [sentences[(num - 1) * 2 % len(sentences)],
                         sentences[((num - 1) * 2 + 1) % len(sentences)]]
                lesson = Lesson(language_id=language.id, level=level, number=num,
                                title=f"{title}")
                session.add(lesson)
                await session.flush()
                for etype, prompt, payload in make_exercises(
                        chunk, sents, rng, lang["code"], num):
                    session.add(Exercise(lesson_id=lesson.id, type=etype,
                                         prompt=prompt, payload=payload))
    await session.commit()
