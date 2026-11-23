const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

const initData = tg.initData || "";

async function api(path, method = "GET", body = null) {
  const res = await fetch("/api" + path, {
    method,
    headers: { "X-Init-Data": initData, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : null,
  });
  if (res.status === 401) {
    showModal("Ошибка авторизации", "Открой приложение через кнопку в чате с ботом @KrolingoBot.");
    throw new Error("auth");
  }
  if (res.status === 402) {
    showScreen("screen-limit");
    throw new Error("limit");
  }
  if (!res.ok) {
    let msg = "Ошибка";
    try { msg = (await res.clone().json()).detail || msg; } catch (_) {
      try { msg = await res.text(); } catch (_) {}
    }
    throw new Error(msg);
  }
  return res.json();
}

function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  document.getElementById("tabbar").style.display =
    ["screen-home", "screen-board", "screen-profile"].includes(id) ? "flex" : "none";
  if (id === "screen-home") setTab("home");
  if (id === "screen-board") setTab("board");
  if (id === "screen-profile") setTab("profile");
}

// Своя модалка в стиле приложения
function showModal(title, text, img = "assets/logo.png") {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-text").innerHTML = text;
  document.getElementById("modal-img").src = img;
  document.getElementById("modal").classList.add("open");
}

document.getElementById("modal-btn").onclick = () =>
  document.getElementById("modal").classList.remove("open");

// Подтверждение (для выхода из урока)
let confirmCb = null;
function showConfirm(title, text, okText, cb) {
  showModal(title, text);
  const btn = document.getElementById("modal-btn");
  btn.textContent = okText;
  confirmCb = cb;
}
const origModalClose = () => {
  document.getElementById("modal").classList.remove("open");
  document.getElementById("modal-btn").textContent = "Понятно";
  if (confirmCb) { const cb = confirmCb; confirmCb = null; cb(); }
};
document.getElementById("modal-btn").onclick = origModalClose;

// ---------- Локализация интерфейса ----------
let uiLang = "ru";

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  const dk = document.getElementById("btn-dontknow");
  if (dk) dk.textContent = t("dont_know");
  const ck = document.getElementById("btn-check");
  if (ck && !ck.dataset.active) ck.textContent = t("check");
}

function setTab(name) {
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.toggle("active", t.dataset.tab === name));
}

document.querySelectorAll(".tab").forEach(t => {
  t.onclick = () => {
    if (t.dataset.tab === "home") goHome();
    if (t.dataset.tab === "board") showBoard();
    if (t.dataset.tab === "profile") showProfile();
  };
});

// ---------- Онбординг ----------
let chosenLang = null;      // один язык (бесплатно)
let chosenLangName = "";
let meCache = null;

async function loadOnboarding() {
  const [langs, me] = await Promise.all([api("/languages"), api("/me")]);
  meCache = me;
  const box = document.getElementById("lang-list");
  box.innerHTML = "";
  document.getElementById("onboarding-hint").textContent =
    me.has_subscription ? t("ob_sub_hint") : t("ob_hint");
  langs.forEach(l => {
    const btn = document.createElement("button");
    btn.className = "card";
    btn.innerHTML = `<span class="flag">${l.code.toUpperCase()}</span> ${l.name}`;
    btn.onclick = () => {
      box.querySelectorAll(".card").forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
      chosenLang = l.id;
      chosenLangName = l.name;
      document.getElementById("btn-start").disabled = false;
    };
    box.appendChild(btn);
  });
  document.getElementById("btn-start").onclick = async () => {
    try {
      await api("/languages", "POST", { language_id: chosenLang });
    } catch (e) {
      if (e.message === "limit") return;
      showModal("Ошибка", "Не удалось сохранить язык. Попробуй ещё раз.");
      return;
    }
    document.getElementById("level-title").textContent =
      t("level_q_named", {name: chosenLangName});
    showScreen("screen-level");
  };
}

// Самооценка → плейсмент-тест
let quizQuestions = [];
let quizIndex = 0;
let quizScore = 0;

document.querySelectorAll("#level-options .card").forEach(btn => {
  btn.onclick = async () => {
    const selfLevel = btn.dataset.level;
    showScreen("screen-loading");
    try {
      const data = await api("/placement/start", "POST",
        { language_id: chosenLang, self_level: selfLevel });
      quizQuestions = data.questions;
      quizIndex = 0;
      quizScore = 0;
      showScreen("screen-quiz");
      renderQuizQuestion();
    } catch (e) {
      if (e.message !== "limit") showModal("Ошибка", "Не удалось загрузить тест. Проверь интернет и попробуй снова.");
    }
  };
});

function renderQuizQuestion() {
  const q = quizQuestions[quizIndex];
  document.getElementById("quiz-progress").style.width =
    (quizIndex / quizQuestions.length * 100) + "%";
  document.getElementById("quiz-step").textContent =
    `Вопрос ${quizIndex + 1} из ${quizQuestions.length}`;
  document.getElementById("quiz-prompt").textContent = q.prompt;
  const box = document.getElementById("quiz-options");
  box.innerHTML = "";
  [...q.payload.options].sort(() => Math.random() - 0.5).forEach(opt => {
    const b = document.createElement("button");
    b.className = "card option";
    b.textContent = opt;
    b.onclick = async () => {
      box.querySelectorAll(".option").forEach(x => {
        x.disabled = true;
        if (x.textContent === q.payload.correct) x.classList.add("correct");
      });
      if (opt === q.payload.correct) {
        quizScore++;
        setTimeout(nextQuizQuestion, 450);
      } else {
        b.classList.add("wrong");
        setTimeout(nextQuizQuestion, 1100);
      }
    };
    box.appendChild(b);
  });
}

async function nextQuizQuestion() {
  quizIndex++;
  if (quizIndex >= quizQuestions.length) {
    document.getElementById("quiz-progress").style.width = "100%";
    const res = await api("/placement/finish", "POST",
      { language_id: chosenLang, score: quizScore });
    document.getElementById("assigned-level").textContent =
      `${res.level} · ${t("lvl_" + res.level)}`;
    showScreen("screen-level-result");
  } else {
    renderQuizQuestion();
  }
}


// ---------- Артикулированный питомец ----------
function renderPet(mood) {
  return `<svg class="pet-svg mood-${mood}" viewBox="0 0 260 300" xmlns="http://www.w3.org/2000/svg">
  <g stroke-linejoin="round" stroke-linecap="round">
  <g id="pet-tail">
    <path d="M 84 236 Q 30 244 20 206 Q 14 182 40 178 Q 62 176 78 196 Z"
          fill="#cf9059" stroke="#5b3a1e" stroke-width="5"/>
  </g>
  <ellipse cx="88" cy="262" rx="42" ry="16" fill="#cf9059" stroke="#5b3a1e" stroke-width="5"/>
  <ellipse cx="176" cy="262" rx="42" ry="16" fill="#cf9059" stroke="#5b3a1e" stroke-width="5"/>
  <g id="pet-body">
    <path d="M 70 250 Q 58 160 96 128 Q 118 112 140 124 Q 186 150 184 222 Q 184 252 158 258 Q 118 266 88 258 Q 74 256 70 250 Z"
          fill="#cf9059" stroke="#5b3a1e" stroke-width="5"/>
    <path d="M 92 236 Q 86 172 112 152 Q 130 142 146 154 Q 168 172 164 226 Q 150 244 128 244 Q 106 244 92 236 Z"
          fill="#f7ead2" stroke="#5b3a1e" stroke-width="4"/>
    <path d="M 102 210 Q 130 226 158 210 Q 152 228 130 230 Q 108 228 102 210 Z"
          fill="#e9d6b4" stroke="#5b3a1e" stroke-width="3.5"/>
    <g id="joey">
      <ellipse cx="130" cy="196" rx="19" ry="17" fill="#cf9059" stroke="#5b3a1e" stroke-width="3.5"/>
      <ellipse cx="130" cy="202" rx="11" ry="8" fill="#f7ead2" stroke="#5b3a1e" stroke-width="2.5"/>
      <ellipse cx="118" cy="178" rx="6" ry="12" fill="#cf9059" stroke="#5b3a1e" stroke-width="2.5" transform="rotate(-14 118 178)"/>
      <ellipse cx="142" cy="178" rx="6" ry="12" fill="#cf9059" stroke="#5b3a1e" stroke-width="2.5" transform="rotate(14 142 178)"/>
      <circle cx="123" cy="192" r="3.4" fill="#2b1a10"/><circle cx="137" cy="192" r="3.4" fill="#2b1a10"/>
      <circle cx="124" cy="191" r="1.1" fill="#fff"/><circle cx="138" cy="191" r="1.1" fill="#fff"/>
      <ellipse cx="130" cy="199" rx="4" ry="3" fill="#5b3a1e"/>
    </g>
  </g>
  <g id="pet-arm-l">
    <path d="M 92 150 Q 76 176 84 200 Q 90 208 98 202 Q 96 178 106 158 Z"
          fill="#cf9059" stroke="#5b3a1e" stroke-width="4.5"/>
  </g>
  <g id="pet-head">
    <g id="ear-l">
      <path d="M 90 62 Q 66 2 92 4 Q 114 8 112 62 Z" fill="#cf9059" stroke="#5b3a1e" stroke-width="5"/>
      <path d="M 95 54 Q 80 14 93 16 Q 105 20 105 56 Z" fill="#efd9b8" stroke="#5b3a1e" stroke-width="3"/>
    </g>
    <g id="ear-r">
      <path d="M 170 62 Q 194 2 168 4 Q 146 8 148 62 Z" fill="#cf9059" stroke="#5b3a1e" stroke-width="5"/>
      <path d="M 165 54 Q 180 14 167 16 Q 155 20 155 56 Z" fill="#efd9b8" stroke="#5b3a1e" stroke-width="3"/>
    </g>
    <path d="M 80 92 Q 76 44 130 42 Q 184 44 180 92 Q 178 122 150 132 Q 130 138 110 132 Q 82 122 80 92 Z"
          fill="#cf9059" stroke="#5b3a1e" stroke-width="5"/>
    <path d="M 96 112 Q 100 132 130 134 Q 160 132 164 112 Q 152 124 130 124 Q 108 124 96 112 Z"
          fill="#f7ead2" stroke="#5b3a1e" stroke-width="4"/>
    <ellipse cx="130" cy="106" rx="13" ry="9" fill="#7a4a26" stroke="#5b3a1e" stroke-width="3.5"/>
    <ellipse cx="102" cy="104" rx="8" ry="5" fill="#f2a0a0" opacity="0.65"/>
    <ellipse cx="158" cy="104" rx="8" ry="5" fill="#f2a0a0" opacity="0.65"/>
    <g id="eyes-open">
      <ellipse cx="106" cy="82" rx="14" ry="16" fill="#fff" stroke="#5b3a1e" stroke-width="3.5"/>
      <ellipse cx="154" cy="82" rx="14" ry="16" fill="#fff" stroke="#5b3a1e" stroke-width="3.5"/>
      <g id="pupils">
        <circle cx="108" cy="84" r="8" fill="#2b1a10"/><circle cx="152" cy="84" r="8" fill="#2b1a10"/>
        <circle cx="105" cy="80" r="3" fill="#fff"/><circle cx="149" cy="80" r="3" fill="#fff"/>
        <circle cx="111" cy="87" r="1.5" fill="#fff" opacity=".8"/><circle cx="155" cy="87" r="1.5" fill="#fff" opacity=".8"/>
      </g>
    </g>
    <g id="eyes-closed">
      <path d="M 94 84 Q 106 76 118 84" stroke="#5b3a1e" stroke-width="5" fill="none"/>
      <path d="M 142 84 Q 154 76 166 84" stroke="#5b3a1e" stroke-width="5" fill="none"/>
    </g>
    <path d="M 118 122 Q 130 130 142 122" stroke="#5b3a1e" stroke-width="5" fill="none"/>
  </g>
  <g id="pet-arm-r">
    <path d="M 168 150 Q 186 174 178 198 Q 172 206 164 200 Q 166 176 156 158 Z"
          fill="#cf9059" stroke="#5b3a1e" stroke-width="4.5"/>
  </g>
  <g id="zzz">
    <text x="196" y="58" font-size="26" font-weight="bold" fill="#9bb7ff">Z</text>
    <text x="214" y="36" font-size="19" font-weight="bold" fill="#b6c8ff">z</text>
    <text x="228" y="20" font-size="14" font-weight="bold" fill="#ccd8ff">z</text>
  </g>
  </g>
</svg>`;
}


function setPet(containerId, mood) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = renderPet(mood);
}

// ---------- Озвучка ----------
let lessonLangCode = "en";
function speak(text, rate = 0.85) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = ({en:"en-US", es:"es-ES", de:"de-DE", fr:"fr-FR", it:"it-IT",
               pt:"pt-BR", tr:"tr-TR", pl:"pl-PL", uk:"uk-UA", ja:"ja-JP"})[lessonLangCode]
             || lessonLangCode;
    u.rate = rate;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch (_) {}
}

function speakerBtn(text, size = 20) {
  const b = document.createElement("button");
  b.className = "icon-btn speak-btn";
  b.innerHTML = `<svg class="ic" style="width:${size}px;height:${size}px"><use href="#i-sound"/></svg>`;
  b.onclick = ev => { ev.stopPropagation(); speak(text); };
  return b;
}

// Позы питомца: случайная из списка
const PET_POSES_ACTIVE = ["sit", "wave", "lie", "think"];
function petPose(active) {
  if (!active) return Math.random() < 0.5 ? "sleep" : "lie";
  return PET_POSES_ACTIVE[Math.floor(Math.random() * PET_POSES_ACTIVE.length)];
}

// Мысли питомца: факты об английском языке
const PET_FACTS = [
  "Знаешь? В английском больше слов, чем в любом другом языке — оценки доходят до миллиона!",
  "Слово «goodbye» — это сокращение от «God be with you» — «да будет Бог с тобой».",
  "Самая частая буква в английском — E. Она составляет около 11% любого текста.",
  "Слово «salary» происходит от латинского salarium — «сольные деньги». Римляне платили солью!",
  "Слово «queue» — пять букв, а произносится только первая. [кью]!",
  "Панграмма «The quick brown fox jumps over the lazy dog» содержит все 26 букв алфавита.",
  "Английский — официальный язык неба: все пилоты мира общаются на нём.",
  "Слово «robot» придумал чешский писатель Карел Чапек в 1920 году.",
  "«Orange» почти не рифмуется ни с чем — поэты его обходят стороной.",
  "Слово «dog» появилось около 1050 года — раньше, чем многие современные слова.",
  "«Typewriter» можно набрать, не убирая пальцев с верхней строки клавиатуры.",
  "Слово «emoji» японское: «э» — картинка, «модзи» — буква. Не имеет отношения к «emotions»!",
  "В словаре Оксфорда самое многозначное слово — «set»: более 400 значений.",
  "Годовщину 25 лет называют silver jubilee, а 50 — golden jubilee.",
  "«Butterfly» — «масляная муха»: возможно, от «butter-colored fly» — «жёлтая, как масло».",
];

const PET_FACTS_EN = [
  "The word 'queue' has five letters but only the first is pronounced!",
  "'Goodbye' is short for 'God be with you'.",
  "The letter E makes up about 11% of any English text.",
  "'Salary' comes from Latin salarium — 'salt money'. Romans paid in salt!",
  "English is the official language of the sky: all pilots speak it.",
  "The word 'robot' was coined by Czech writer Karel Capek in 1920.",
  "'Typewriter' can be typed using only the top keyboard row.",
  "In the Oxford dictionary, 'set' has over 400 meanings.",
  "No word rhymes with 'orange' — poets avoid it.",
  "'Butterfly' may come from 'butter-colored fly' — yellow like butter.",
];
const WORD_EMOJI = {
  "cat": "🐱", "dog": "🐶", "sun": "☀️", "water": "💧", "apple": "🍎",
  "book": "📖", "house": "🏠", "milk": "🥛", "bread": "🍞", "tree": "🌳",
  "friend": "🧑‍🤝‍🧑", "school": "🏫", "city": "🏙️", "river": "🏞️", "music": "🎵",
  "hand": "✋", "day": "📅", "night": "🌙", "family": "👨‍👩‍👧", "time": "⏰",
  "run": "🏃", "eat": "🍽️", "drink": "🥤", "sleep": "😴", "read": "📚",
  "write": "✍️", "red": "🔴", "blue": "🔵", "green": "🟢", "white": "⚪",
  "big": "🐘", "small": "🐭", "happy": "😊", "good": "👍", "new": "✨",
  "old": "🧓", "shop": "🛒", "money": "💰", "price": "🏷️", "menu": "📋",
  "bus": "🚌", "train": "🚆", "ticket": "🎫", "hotel": "🏨", "rain": "🌧️",
  "snow": "❄️", "wind": "💨", "game": "🎮", "party": "🎉", "gift": "🎁",
};

// ---------- Главная ----------
async function goHome() {
  showScreen("screen-loading");
  const [me, progress] = await Promise.all([api("/me"), api("/progress")]);
  uiLang = me.ui_language || "ru";
  applyI18n();
  document.getElementById("streak").textContent = me.streak;
  document.getElementById("xp").textContent = me.xp;
  document.getElementById("limit-info").textContent = me.has_subscription
    ? t("sub_left", {n: me.subscription_days_left})
    : t("today_limit", {a: progress.lessons_done_today, b: progress.free_daily_limit});

  setPet("home-pet", me.pet_mood === "happy" ? "happy" : "sleep");
  const homePet = document.getElementById("home-pet");
  homePet.classList.toggle("super", me.streak >= 7);
  const poses = ["pose-hop", "pose-sway", "pose-calm", ""];
  homePet.className = "home-pet " + (me.streak >= 7 ? "super"
    : poses[Math.floor(Math.random() * poses.length)]);
  const facts = (uiLang === "ru") ? PET_FACTS : PET_FACTS_EN;
  // трансляция от админа видна всем вместо факта, пока не истечёт
  const thought = me.broadcast
    ? "📢 " + me.broadcast
    : facts[Math.floor(Math.random() * facts.length)];
  document.getElementById("pet-thought").textContent =
    (me.pet_mood === "happy" || me.broadcast ? "" : t("thought_sad")) + thought;

  const list = document.getElementById("progress-list");
  list.innerHTML = "";
  if (progress.items.length === 0) {
    await loadOnboarding();
    showScreen("screen-onboarding");
    return;
  }
  gameLangId = progress.items[0].language_id;
  renderGameStrip();
  progress.items.forEach(item => {
    list.appendChild(renderPath(item, progress.can_start));
  });
  if (me.has_subscription) {
    const add = document.createElement("button");
    add.className = "card";
    add.innerHTML = `<b>${t("add_lang")}</b>`;
    add.onclick = async () => { await loadOnboarding(); showScreen("screen-onboarding"); };
    list.appendChild(add);
  }
  showScreen("screen-home");
}

function renderPath(item, canStart) {
  const wrap = document.createElement("div");
  wrap.className = "path-wrap";
  const toNext = item.level_total - item.level_done;
  const lvlName = t("lvl_" + item.level);
  wrap.innerHTML = `<div class="path-header">
      <b>${item.language_name} · ${item.level} (${lvlName})</b><br>
      <span class="path-progress-line">${t("to_next", {n: toNext})}</span>
    </div>`;
  const path = document.createElement("div");
  path.className = "path";
  item.path.forEach((node, i) => {
    if (i > 0) {
      const conn = document.createElement("div");
      conn.className = "path-connector";
      path.appendChild(conn);
    }
    if (i > 0 && i % 10 === 0) {
      const chest = document.createElement("button");
      chest.className = "path-node path-chest";
      chest.innerHTML = '<svg class="ic" style="width:28px;height:28px"><use href="#i-star"/></svg>';
      chest.onclick = openChest;
      path.appendChild(chest);
      const conn2 = document.createElement("div");
      conn2.className = "path-connector";
      path.appendChild(conn2);
    }
    const btn = document.createElement("button");
    const isCurrent = !node.done && (i === 0 || item.path[i - 1].done);
    btn.className = "path-node " + (node.done ? "done" : (isCurrent && canStart ? "current" : "locked"));
    btn.textContent = node.done ? "✓" : node.number;
    if (node.done) btn.onclick = () => startRepeat(node.lesson_id);
    else if (isCurrent && canStart) btn.onclick = () => startLesson(item.language_id);
    else if (isCurrent && !canStart) btn.onclick = () => showScreen("screen-limit");
    path.appendChild(btn);
  });
  if (item.exam_open) {
    const conn = document.createElement("div");
    conn.className = "path-connector";
    path.appendChild(conn);
    const exam = document.createElement("button");
    exam.className = "path-node path-exam";
    exam.innerHTML = `<svg class="ic" style="width:26px;height:26px"><use href="#i-crown"/></svg>`;
    exam.onclick = () => startExam(item.language_id);
    path.appendChild(exam);
  }
  wrap.appendChild(path);
  return wrap;
}

// ---------- Урок ----------
let lesson = null;
let lessonLangId = null;
let exIndex = 0;
let selectedOption = null;
let correctCount = 0;
let retryQueue = [];      // задания, где нажали «Не знаю»
let retryRound = false;
let mistakes = [];        // ошибки текущего урока: {prompt, your}

async function startLesson(languageId) {
  lessonLangId = languageId;
  try {
    lesson = await api(`/lesson/${languageId}`);
  } catch (e) { if (e.message !== "limit") showModal("Ошибка", "Не удалось загрузить урок. Попробуй ещё раз."); return; }
  startLessonFlow();
}

async function startRepeat(lessonId) {
  try {
    lesson = await api(`/repeat/${lessonId}`);
  } catch (e) { if (e.message !== "limit") showModal("Ошибка", "Не удалось загрузить урок. Попробуй ещё раз."); return; }
  startLessonFlow();
}

function startLessonFlow() {
  exIndex = 0;
  correctCount = 0;
  retryQueue = [];
  retryRound = false;
  mistakes = [];
  if (lesson.lang) lessonLangCode = lesson.lang;
  // экран теории (если есть)
  if (lesson.theory && !lesson.repeat) {
    document.getElementById("theory-title").textContent = lesson.theory.title;
    const body = document.getElementById("theory-body");
    body.innerHTML = "";
    (lesson.theory.blocks || []).forEach(b => {
      const div = document.createElement("div");
      div.className = "theory-block";
      div.innerHTML = `<h3>${b.h}</h3><p>${b.p}</p>`;
      body.appendChild(div);
    });
    document.getElementById("btn-theory-next").onclick = showIntroOrLesson;
    showScreen("screen-theory");
    return;
  }
  showIntroOrLesson();
}

function showIntroOrLesson() {
  // экран знакомства со словами
  const intro = lesson.intro_words || [];
  if (intro.length && !lesson.repeat) {
    setPet("intro-pet", "happy");
    document.getElementById("intro-title").textContent =
      `${lesson.title} · ${lesson.level}`;
    const grid = document.getElementById("intro-words");
    grid.innerHTML = "";
    intro.forEach(([word, trans], i) => {
      const card = document.createElement("div");
      card.className = "word-card";
      card.style.animationDelay = (i * 0.07) + "s";
      card.innerHTML = `<div class="w-num">${i + 1}</div>
        <div style="flex:1"><div class="w-word">${word}</div><div class="w-trans">${trans}</div></div>`;
      card.appendChild(speakerBtn(word, 18));
      grid.appendChild(card);
    });
    document.getElementById("btn-intro-start").onclick = () => {
      document.getElementById("lesson-title").textContent = lesson.title;
      showScreen("screen-lesson");
      renderExercise();
    };
    showScreen("screen-intro");
    return;
  }
  document.getElementById("lesson-title").textContent = lesson.title;
  showScreen("screen-lesson");
  renderExercise();
}

// ---------- Экзамен ----------
let examQuestions = [];
let examIndex = 0;
let examScore = 0;
let examLang = null;

async function startExam(languageId) {
  examLang = languageId;
  try {
    const data = await api(`/exam/${languageId}`);
    examQuestions = data.questions;
    examIndex = 0;
    examScore = 0;
    showScreen("screen-exam");
    renderExamQuestion();
  } catch (e) {
    if (e.message !== "limit") showModal("Ошибка", "Не удалось загрузить экзамен.");
  }
}

function renderExamQuestion() {
  const q = examQuestions[examIndex];
  document.getElementById("exam-progress").style.width =
    (examIndex / examQuestions.length * 100) + "%";
  document.getElementById("exam-step").textContent =
    t("exam_step", {a: examIndex + 1, b: examQuestions.length});
  document.getElementById("exam-prompt").textContent = q.prompt;
  const sent = document.getElementById("exam-sentence");
  if (q.type === "gap" && q.sentence) {
    sent.style.display = "";
    sent.textContent = q.sentence;
  } else {
    sent.style.display = "none";
  }
  const box = document.getElementById("exam-options");
  box.innerHTML = "";
  [...q.payload.options].sort(() => Math.random() - 0.5).forEach(opt => {
    const b = document.createElement("button");
    b.className = "card option";
    b.textContent = opt;
    b.onclick = async () => {
      box.querySelectorAll(".option").forEach(x => {
        x.disabled = true;
        if (x.textContent === q.payload.correct) x.classList.add("correct");
      });
      if (opt === q.payload.correct) {
        examScore++;
        setTimeout(nextExamQuestion, 450);
      } else {
        b.classList.add("wrong");
        setTimeout(nextExamQuestion, 1100);
      }
    };
    box.appendChild(b);
  });
}

async function nextExamQuestion() {
  examIndex++;
  if (examIndex >= examQuestions.length) {
    document.getElementById("exam-progress").style.width = "100%";
    const res = await api(`/exam/${examLang}/finish`, "POST",
      { score: examScore, total: examQuestions.length });
    if (res.passed) {
      showModal(t("exam_passed"),
        t("exam_passed_t", {p: res.percent, l: res.level, ln: t("lvl_" + res.level)}),
        "assets/pet_happy.svg");
    } else {
      showModal(t("exam_failed"),
        t("exam_failed_t", {p: res.percent}),
        "assets/pet_sad.svg");
    }
    goHome();
  } else {
    renderExamQuestion();
  }
}

function renderExercise() {
  selectedOption = null;
  const fb = document.getElementById("feedback-bar");
  if (fb) fb.remove();
  const ex = lesson.exercises[exIndex];
  const total = lesson.exercises.length;
  document.getElementById("lesson-progress").style.width =
    (exIndex / total * 100) + "%";
  let promptHtml = `<p class="muted">${exIndex + 1} / ${total}${retryRound ? " · повтор" : ""}</p><h2>${ex.prompt}</h2>`;
  if (ex.type === "gap" && ex.payload.sentence) {
    promptHtml += `<p class="sentence-text">${ex.payload.sentence}</p>`;
  }
  document.getElementById("exercise-box").innerHTML = promptHtml;

  const box = document.getElementById("exercise-options");
  box.innerHTML = "";
  const checkBtn = document.getElementById("btn-check");
  checkBtn.style.display = "";
  checkBtn.disabled = false;
  checkBtn.textContent = t("check");
  checkBtn.onclick = () => checkAnswer(ex);

  const dontKnowBtn = document.getElementById("btn-dontknow");
  if (ex.type === "pairs") {
    dontKnowBtn.style.display = "none";
    renderPairs(ex, box);
    checkBtn.style.display = "none";
  } else {
    dontKnowBtn.style.display = "";
    dontKnowBtn.textContent = t("dont_know");
    dontKnowBtn.disabled = false;
    dontKnowBtn.onclick = () => dontKnow(ex);
    if (ex.type === "sentence") {
      renderSentence(ex, box);
    } else {
      const options = [...ex.payload.options].sort(() => Math.random() - 0.5);
      options.forEach(opt => {
        const btn = document.createElement("button");
        btn.className = "card option";
        btn.textContent = opt;
        btn.onclick = () => {
          box.querySelectorAll(".option").forEach(b => b.classList.remove("selected"));
          btn.classList.add("selected");
          selectedOption = opt;
        };
        box.appendChild(btn);
      });
    }
  }
}

// «Не знаю»: показываем ответ, задание уйдёт в повторную очередь
function dontKnow(ex) {
  mistakes.push({ prompt: ex.prompt, your: "—" });
  const box = document.getElementById("exercise-options");
  box.querySelectorAll(".option").forEach(b => {
    b.disabled = true;
    if (b.textContent === ex.payload.correct) b.classList.add("correct");
  });
  const line = document.getElementById("sentence-line");
  if (line) line.classList.add("revealed");
  if (!retryRound) retryQueue.push(ex);
  const checkBtn = document.getElementById("btn-check");
  checkBtn.textContent = t("next");
  checkBtn.onclick = nextExercise;
  document.getElementById("btn-dontknow").disabled = true;
}

function renderPairs(ex, box) {
  const flat = ex.payload.pairs.flat().sort(() => Math.random() - 0.5);
  let first = null, matched = 0;
  flat.forEach(word => {
    const btn = document.createElement("button");
    btn.className = "card option";
    btn.style.justifyContent = "center";
    btn.textContent = word;
    btn.onclick = () => {
      if (btn.classList.contains("correct")) return;
      if (!first) { first = btn; btn.classList.add("selected"); return; }
      const isPair = ex.payload.pairs.some(p => p.includes(first.textContent) && p.includes(word));
      if (isPair) {
        btn.classList.add("correct"); first.classList.remove("selected"); first.classList.add("correct");
        first = null;
        if (++matched * 2 === flat.length) setTimeout(nextExercise, 500);
      } else {
        first.classList.remove("selected");
        btn.classList.add("wrong");
        setTimeout(() => btn.classList.remove("wrong"), 400);
        first = null;
      }
    };
    box.appendChild(btn);
  });
}

// Сборка предложения из слов
let placedWords = [];

function renderSentence(ex, box) {
  placedWords = [];
  const wrap = document.createElement("div");

  const line = document.createElement("div");
  line.className = "sentence-line";
  line.id = "sentence-line";

  const bank = document.createElement("div");
  bank.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;";
  const bankWords = [...ex.payload.bank].sort(() => Math.random() - 0.5);
  bankWords.forEach(w => {
    const chip = document.createElement("button");
    chip.className = "word-chip";
    chip.textContent = w;
    chip.onclick = () => {
      if (chip.classList.contains("used")) return;
      chip.classList.add("used");
      addPlaced(ex, line, chip.textContent, chip);
    };
    bank.appendChild(chip);
  });

  wrap.appendChild(line);
  wrap.appendChild(bank);
  box.appendChild(wrap);
}

function addPlaced(ex, line, word, sourceChip) {
  const chip = document.createElement("button");
  chip.className = "word-chip placed";
  chip.textContent = word;
  chip.onclick = () => {
    placedWords = placedWords.filter(w => w !== word || chip.dataset.taken);
    chip.remove();
    sourceChip.classList.remove("used");
  };
  line.appendChild(chip);
}

function getSentenceAnswer() {
  const line = document.getElementById("sentence-line");
  return line ? [...line.querySelectorAll(".placed")].map(c => c.textContent).join(" ") : "";
}

function showFeedback(ok, ex) {
  const old = document.getElementById("feedback-bar");
  if (old) old.remove();
  const bar = document.createElement("div");
  bar.id = "feedback-bar";
  bar.className = "feedback-bar " + (ok ? "ok" : "bad");
  let html = ok ? "<b>Верно!</b>" : `<b>Неверно.</b> Правильный ответ: «${ex.payload.correct}»`;
  if (ex.payload.src) html += `<div class="feedback-src">${ex.payload.src}</div>`;
  bar.innerHTML = html;
  const actions = document.querySelector(".lesson-actions");
  actions.parentNode.insertBefore(bar, actions);
}

function checkAnswer(ex) {
  if (ex.type === "sentence") {
    selectedOption = getSentenceAnswer();
    if (!selectedOption) return;
  }
  if (ex.type === "dictation") {
    // selectedOption уже установлен в renderDictation
  } else if (selectedOption === null || selectedOption === undefined) return;

  const correct = ex.payload.correct;
  const ok = ex.type === "sentence" || ex.type === "dictation"
    ? selectedOption.trim().toLowerCase() === correct.trim().toLowerCase()
    : selectedOption === correct;

  const box = document.getElementById("exercise-options");
  box.querySelectorAll(".option").forEach(b => {
    if (b.textContent === correct) b.classList.add("correct");
  });

  showFeedback(ok, ex);
  if (ex.payload.correct && (ex.type === "sentence" || ex.type === "gap"
      || (ok && ex.type === "choice"))) {
    speak(ex.payload.correct, 0.9);
  }

  const checkBtn = document.getElementById("btn-check");
  if (!ok) {
    mistakes.push({ prompt: ex.prompt, your: selectedOption });
    if (ex.type === "sentence" || ex.type === "dictation") {
      checkBtn.textContent = t("next");
      checkBtn.onclick = nextExercise;
      return;
    }
    box.querySelectorAll(".option").forEach(b => {
      if (b.textContent === selectedOption) b.classList.add("wrong");
    });
    checkBtn.textContent = t("next");
    checkBtn.onclick = nextExercise;
  } else {
    correctCount++;
    nextExercise();
  }
}

async function nextExercise() {
  exIndex++;
  document.getElementById("btn-check").textContent = t("check");
  if (exIndex >= lesson.exercises.length) {
    if (!retryRound && retryQueue.length) {
      // второй круг: прогоняем задания, где было «Не знаю»
      retryRound = true;
      lesson = { ...lesson, exercises: retryQueue };
      exIndex = 0;
      showModal(t("next"), "");
      renderExercise();
      return;
    }
    document.getElementById("lesson-progress").style.width = "100%";
    const result = await api(`/lesson/${lesson.lesson_id}/complete`, "POST");
    if (result.gift) {
      setTimeout(() => showModal(t("gift_title"),
        t("gift_text", {n: result.streak}),
        "assets/pet_happy.svg"), 400);
    } else if (result.level && !lesson.repeat && result.level !== lesson.level) {
      setTimeout(() => showModal(t("level_up"),
        t("level_up_t", {l: result.level}), "assets/pet_happy.svg"), 400);
    }
    document.getElementById("res-correct").textContent =
      `${correctCount}/${lesson.exercises.length}`;
    document.getElementById("res-streak").textContent = result.streak;
    document.getElementById("res-xp").textContent = result.xp;
    renderMistakes();
    showScreen("screen-result");
  } else {
    renderExercise();
  }
}

// ---------- Рейтинг ----------
async function showBoard() {
  showScreen("screen-loading");
  const data = await api("/leaderboard");
  const list = document.getElementById("board-list");
  list.innerHTML = "";
  const medals = ["", "", ""];
  data.items.forEach(item => {
    const row = document.createElement("div");
    row.className = "card board-row" +
      (item.rank <= 3 ? " first" : "") + (item.is_me ? " board-me" : "");
    row.innerHTML = `
      <div class="board-rank">${item.rank <= 3
        ? `<svg class="ic" style="${item.rank === 1 ? '' : 'opacity:' + (0.9 - item.rank * 0.25)}"><use href="#i-crown"/></svg>`
        : item.rank}</div>
      <div class="board-name">${item.name}${item.is_me ? " " + t("you") : ""}</div>
      <div class="board-xp">${item.xp}<svg class="ic gem" style="width:16px;height:16px"><use href="#i-gem"/></svg></div>`;
    list.appendChild(row);
  });
  showScreen("screen-board");
}

// ---------- Профиль ----------
// Стадии роста питомца по XP: детёныш -> мудрец
const GROWTH_STAGES = [
  { min: 0, key: "growth_1" },
  { min: 100, key: "growth_2" },
  { min: 500, key: "growth_3" },
  { min: 1500, key: "growth_4" },
];
const GROWTH_SIZES = [130, 160, 190, 215];

async function showProfile() {
  showScreen("screen-loading");
  const [me, board, progress, history] = await Promise.all(
    [api("/me"), api("/leaderboard"), api("/progress"), api("/history")]);
  let mood, caption;
  if (me.streak >= 7) {
    mood = "happy";
    caption = t("pet_proud", {n: me.streak});
  } else if (me.pet_mood === "happy") {
    mood = "happy";
    caption = me.lessons_done_today > 0 ? t("pet_today")
      : (me.streak >= 3 ? t("pet_streak", {n: me.streak}) : t("pet_idle"));
  } else {
    mood = "sleep";
    caption = me.streak >= 7 ? t("pet_sleep_streak", {n: me.streak}) : t("pet_sleep");
  }
  setPet("profile-pet", mood);
  const petEl = document.getElementById("profile-pet");
  petEl.classList.toggle("super", me.streak >= 7);
  // рост питомца: стадия зависит от XP — чем больше опыта, тем взрослее
  const stageIdx = GROWTH_STAGES.reduce(
    (acc, s, i) => (me.xp >= s.min ? i : acc), 0);
  const stage = GROWTH_STAGES[stageIdx];
  const nextStage = GROWTH_STAGES[stageIdx + 1];
  petEl.style.width = petEl.style.height = GROWTH_SIZES[stageIdx] + "px";
  // полноценная картинка маскота (реалистичная модель, прозрачный фон)
  petEl.innerHTML = `<img class="profile-pet-img" src="assets/kangaroo_real.png" alt="Kengo">`;
  document.getElementById("growth-label").textContent = nextStage
    ? `🌱 ${t(stage.key)} · ${t("growth_to", {n: nextStage.min - me.xp, s: t(nextStage.key)})}`
    : `🏆 ${t(stage.key)}`;
  const prevMin = stage.min;
  const pct = nextStage
    ? Math.min(100, Math.round((me.xp - prevMin) / (nextStage.min - prevMin) * 100))
    : 100;
  document.getElementById("growth-progress").style.width = pct + "%";
  document.getElementById("pet-caption").textContent = caption;
  const nameEl = document.getElementById("profile-name");
  nameEl.innerHTML = "";
  nameEl.textContent = me.first_name || "Ученик";
  const editBtn = document.createElement("button");
  editBtn.className = "icon-btn";
  editBtn.innerHTML = '<svg class="ic" style="width:16px;height:16px"><use href="#i-edit"/></svg>';
  editBtn.onclick = editNickname;
  nameEl.appendChild(editBtn);
  const lessonsDone = progress.items.filter(i => i.completed).length;
  document.getElementById("profile-name").textContent = me.first_name || "Ученик";
  document.getElementById("profile-sub").textContent = me.has_subscription
    ? t("sub_left", {n: me.subscription_days_left}) : t("free_account");
  document.getElementById("p-xp").textContent = me.xp;
  document.getElementById("p-streak").textContent = me.streak;
  document.getElementById("p-lessons").textContent = history.items.length;
  document.getElementById("p-rank").textContent = board.my_rank;
  document.getElementById("btn-p-stats").onclick = () => showScreen("screen-p-stats");
  document.getElementById("btn-p-lang").onclick = () => showScreen("screen-p-lang");
  document.getElementById("btn-p-history").onclick = () => showScreen("screen-p-history");
  document.getElementById("btn-p-settings").onclick = () => showScreen("screen-p-settings");
  document.getElementById("btn-share").onclick = () => {
    const text = t("share_text", {n: me.streak});
    tg.openTelegramLink(
      `https://t.me/share/url?url=${encodeURIComponent("https://t.me/KrolingoBot")}&text=${encodeURIComponent(text)}`);
  };
  if (!me.has_subscription) {
    let banner = document.getElementById("sub-banner");
    if (!banner) {
      banner = document.createElement("button");
      banner.id = "sub-banner";
      banner.className = "sub-banner";
      banner.innerHTML = `<svg class="ic" style="width:30px;height:30px"><use href="#i-star"/></svg>
        <div style="flex:1"><b>${t("sub_banner_t")}</b><br>
        <span>${t("sub_banner_s")}</span></div>`;
      document.querySelector("#screen-profile .profile-card").after(banner);
    }
    banner.onclick = showPlans;
  }

  const hlist = document.getElementById("history-list");
  hlist.innerHTML = "";
  if (!history.items.length) {
    hlist.innerHTML = `<p class="muted">${t("history_empty")}</p>`;
  }
  history.items.forEach(h => {
    const row = document.createElement("button");
    row.className = "card";
    row.innerHTML = `<div style="flex:1">
        <b>${h.title}</b><br>
        <span class="muted" style="margin:0">${h.language_name} · ${h.level} · ${h.completed_at}</span>
      </div>
      <svg class="ic"><use href="#i-play"/></svg>`;
    row.onclick = () => startRepeat(h.lesson_id);
    hlist.appendChild(row);
  });
  showScreen("screen-profile");
}

// ---------- Подписка ----------
const STAR_SVG = '<svg style="width:18px;height:18px;vertical-align:-3px"><use href="#i-star"/></svg>';

function perksHtml() {
  const perks = [t("perk_1"), t("perk_2"), t("perk_3"), t("perk_4"), t("perk_5")];
  return perks.map(p =>
    `<div class="perk-row"><svg class="ic" style="width:20px;height:20px;color:var(--green)"><use href="#i-check"/></svg> ${p}</div>`
  ).join("");
}

async function showPlans() {
  showScreen("screen-loading");
  const plans = await api("/plans");
  document.getElementById("plans-perks").innerHTML = perksHtml();
  const list = document.getElementById("plans-list");
  list.innerHTML = "";
  plans.forEach(p => {
    const btn = document.createElement("button");
    btn.className = "card";
    btn.innerHTML = `<svg class="ic"><use href="#i-star"/></svg>
      <div style="flex:1"><b>${p.title}</b><br>
      <span class="muted" style="margin:0">Безлимитные уроки на ${p.days} дней</span></div>
      <b style="color:var(--gold);display:flex;align-items:center;gap:3px">${STAR_SVG} ${p.stars}</b>`;
    btn.onclick = async () => {
      try {
        const res = await api("/buy", "POST", { plan: p.key });
        if (tg.openInvoice) {
          tg.openInvoice(res.url, status => {
            if (status === "paid") {
              showModal("Подписка активна!", "Добро пожаловать в Krolingo Premium!", "assets/logo.png");
              goHome();
            } else if (status === "failed") {
              showModal("Оплата не прошла", "Попробуй ещё раз чуть позже.");
            }
          });
        } else {
          tg.openLink(res.url);
        }
      } catch (e) {
        if (e.message !== "limit") showModal("Ошибка", e.message || "Не удалось создать инвойс");
      }
    };
    list.appendChild(btn);
  });
  showScreen("screen-plans");
}

document.getElementById("btn-plans").onclick = showPlans;

// ---------- Старт ----------
(async () => {
  try {
    await loadOnboarding();
    await goHome();
  } catch (e) {
    if (e.message !== "limit" && e.message !== "auth") showModal("Ошибка", "Что-то пошло не так при загрузке.");
  }
})();

// ---------- Сундук ----------
async function openChest() {
  try {
    const res = await api("/chest", "POST");
    showModal("Сундук открыт!", `Внутри <b>+${res.granted} XP</b>! Всего: ${res.xp}.`, "assets/logo.png");
    goHome();
  } catch (e) {
    if (e.message !== "limit") {
      showConfirm(t("chest_locked"), e.message + t("chest_offer"), t("view_plans"), showPlans);
    }
  }
}

// ---------- Ошибки урока ----------
function renderMistakes() {
  const box = document.getElementById("mistakes-box");
  const list = document.getElementById("mistakes-list");
  list.innerHTML = "";
  if (!mistakes.length) { box.style.display = "none"; return; }
  box.style.display = "";
  mistakes.forEach(m => {
    const card = document.createElement("div");
    card.className = "mistake-card";
    card.innerHTML = `<div class="m-q">${m.prompt}</div>
      <div class="m-a">${t("your_answer")}: ${m.your}</div>`;
    list.appendChild(card);
  });
}

// ---------- Выход из урока ----------
function exitLesson() {
  showConfirm(t("exit_title"), t("exit_text"), t("exit_ok"), () => goHome());
}

// ---------- Язык интерфейса ----------
async function showUiLanguages() {
  showScreen("screen-loading");
  const langs = await api("/ui_languages");
  const me = await api("/me");
  const list = document.getElementById("ui-lang-list");
  list.innerHTML = "";
  langs.forEach(l => {
    const btn = document.createElement("button");
    btn.className = "card" + ((me.ui_language || "ru") === l.code ? " selected" : "");
    btn.innerHTML = `<b style="flex:1">${l.name}</b>
      <span style="color:var(--muted)">${l.code}</span>`;
    btn.onclick = async () => {
      await api("/me", "PATCH", { ui_language: l.code });
      uiLang = l.code;
      applyI18n();
      showProfile();
    };
    list.appendChild(btn);
  });
  showScreen("screen-language");
}

// ---------- Игры ----------
let gameLangId = null;

async function showGames() {
  showScreen("screen-loading");
  const progress = await api("/progress");
  const list = document.getElementById("games-list");
  list.innerHTML = "";
  if (!progress.items.length) {
    list.innerHTML = `<p class="muted">${t("games_notyet")}</p>`;
    showScreen("screen-games");
    return;
  }
  gameLangId = progress.items[0].language_id;

  games.forEach(g => {
    const btn = document.createElement("button");
    btn.className = "game-card";
    btn.innerHTML = `<svg class="ic" style="width:30px;height:30px"><use href="#i-target"/></svg>
      <div><b>${g.name}</b><p class="muted">${g.desc}</p></div>`;
    btn.onclick = () => g.id === "sprint" ? startSprint() : startAnagram();
    list.appendChild(btn);
  });
  showScreen("screen-games");
}

// Спринт
let sprintPairs = [], sprintIdx = 0, sprintScore = 0, sprintTimer = null;
let sprintCurrentTrue = false;

async function startSprint() {
  const data = await api(`/game/words/${gameLangId}?n=40`);
  sprintPairs = data.pairs;
  sprintIdx = 0; sprintScore = 0;
  document.getElementById("sprint-score").textContent = "0";
  showScreen("screen-sprint");
  let time = 45;
  const timerEl = document.getElementById("sprint-timer");
  timerEl.textContent = time;
  timerEl.classList.remove("low");
  nextSprintRound();
  clearInterval(sprintTimer);
  sprintTimer = setInterval(() => {
    time--;
    timerEl.textContent = time;
    if (time <= 10) timerEl.classList.add("low");
    if (time <= 0) endSprint();
  }, 1000);
}

function nextSprintRound() {
  if (sprintIdx >= sprintPairs.length) {
    const shuffled = [...sprintPairs].sort(() => Math.random() - 0.5);
    sprintPairs = shuffled;
    sprintIdx = 0;
  }
  const pair = sprintPairs[sprintIdx++];
  sprintCurrentTrue = Math.random() < 0.5;
  let shown = pair.translation;
  if (!sprintCurrentTrue) {
    // подмена переводом другого слова
    const other = sprintPairs[Math.floor(Math.random() * sprintPairs.length)];
    if (other.word === pair.word || other.translation === pair.translation) {
      sprintCurrentTrue = true;
    } else {
      shown = other.translation;
    }
  }
  document.getElementById("sprint-word").textContent = pair.word;
  document.getElementById("sprint-trans").textContent = shown;
}

function sprintAnswer(saidTrue) {
  if (saidTrue === sprintCurrentTrue) {
    sprintScore++;
    document.getElementById("sprint-score").textContent = sprintScore;
    nextSprintRound();
  } else {
    endSprint();
  }
}

async function endSprint() {
  clearInterval(sprintTimer);
  const gained = Math.min(sprintScore, 30);
  const res = await api("/game/xp", "POST", { points: gained });
  showModal(t("sprint_end"),
    `${t("correct_answers")}: <b>${sprintScore}</b>.<br>${t("earned")}: <b>+${res.granted} XP</b>${res.multiplier === 2 ? " (×2!)" : ""}!`,
    "assets/pet_happy.svg");
  goHome();
}

document.getElementById("btn-sprint-yes").onclick = () => sprintAnswer(true);
document.getElementById("btn-sprint-no").onclick = () => sprintAnswer(false);

// Анаграммы
let anagramWord = "", anagramPlaced = [];

async function startAnagram() {
  const data = await api(`/game/words/${gameLangId}?n=1`);
  const pair = data.pairs[0];
  anagramWord = pair.word;
  anagramPlaced = [];
  document.getElementById("anagram-trans").textContent = pair.translation;
  const bank = document.getElementById("anagram-bank");
  bank.innerHTML = "";
  const letters = anagramWord.split("").map((ch, i) => ({ ch, id: i }))
    .sort(() => Math.random() - 0.5);
  letters.forEach(({ ch, id }) => {
    const b = document.createElement("button");
    b.className = "letter-chip";
    b.textContent = ch;
    b.dataset.id = id;
    b.onclick = () => {
      if (b.disabled) return;
      b.disabled = true;
      anagramPlaced.push({ ch, id, src: b });
      renderAnagram();
    };
    bank.appendChild(b);
  });
  renderAnagram();
  showScreen("screen-anagram");
}

function renderAnagram() {
  const slots = document.getElementById("anagram-slots");
  slots.innerHTML = "";
  anagramPlaced.forEach((p, idx) => {
    const b = document.createElement("button");
    b.className = "letter-chip";
    b.textContent = p.ch;
    b.onclick = () => {
      anagramPlaced.splice(idx, 1);
      p.src.disabled = false;
      renderAnagram();
    };
    slots.appendChild(b);
  });
}

document.getElementById("btn-anagram-reset").onclick = () => {
  anagramPlaced = [];
  document.querySelectorAll("#anagram-bank .letter-chip").forEach(b => b.disabled = false);
  renderAnagram();
};

document.getElementById("btn-anagram-check").onclick = async () => {
  const attempt = anagramPlaced.map(p => p.ch).join("");
  if (attempt.length !== anagramWord.length) return;
  if (attempt.toLowerCase() === anagramWord.toLowerCase()) {
    const res = await api("/game/xp", "POST", { points: 3 });
    showModal("Верно!", `«${anagramWord}» — правильно! <b>+3 XP</b>`, "assets/pet_happy.svg");
  } else {
    showModal("Почти!", `Получилось «${attempt}». Попробуй иначе!`, "assets/pet_sad.svg");
  }
  startAnagram();
};

document.getElementById("btn-ui-lang").onclick = showUiLanguages;

// ---------- Смена языка обучения ----------
async function showChangeLanguage() {
  showScreen("screen-loading");
  const [langs, me, progress] = await Promise.all(
    [api("/languages"), api("/me"), api("/progress")]);
  const current = progress.items.length ? progress.items[0].language_id : null;
  document.getElementById("change-lang-hint").textContent = me.has_subscription
    ? "С подпиской меняй язык когда угодно."
    : "Бесплатно — раз в 7 дней. С подпиской — без ожидания.";
  const list = document.getElementById("change-lang-list");
  list.innerHTML = "";
  langs.forEach(l => {
    const btn = document.createElement("button");
    btn.className = "card" + (l.id === current ? " selected" : "");
    btn.innerHTML = `<span class="flag">${l.code.toUpperCase()}</span>
      <b style="flex:1">${l.name}</b>
      ${l.id === current ? '<span style="color:var(--green)">текущий</span>' : ""}`;
    if (l.id !== current) {
      btn.onclick = async () => {
        try {
          await api("/language/change", "POST", { language_id: l.id });
          // заново определяем уровень: самооценка -> мини-тест
          chosenLang = l.id;
          chosenLangName = l.name;
          document.getElementById("level-title").textContent =
            t("level_q_named", {name: l.name});
          showScreen("screen-level");
        } catch (e) {
          if (e.message !== "limit") showModal("Пока нельзя", e.message || "Смена недоступна", "assets/pet_sleep.svg");
        }
      };
    }
    list.appendChild(btn);
  });
  showScreen("screen-change-lang");
}

document.getElementById("btn-change-lang").onclick = showChangeLanguage;

// ---------- Игровая полоса на главной ----------
function renderGameStrip() {
  const strip = document.getElementById("game-strip");
  if (!strip) return;
  strip.innerHTML = "";
    const games = [
    { id: "sprint", name: t("game_sprint"), icon: "i-flame" },
    { id: "anagram", name: t("game_anagram"), icon: "i-book" },
    { id: "pairs", name: t("game_pairs"), icon: "i-target" },
    { id: "quizgame", name: t("game_quiz"), icon: "i-crown" },
  ];
  games.forEach(g => {
    const b = document.createElement("button");
    b.className = "game-chip";
    b.innerHTML = `<svg class="ic"><use href="#${g.icon}"/></svg>${g.name}`;
    b.onclick = () => {
      if (g.id === "sprint") startSprint();
      else if (g.id === "anagram") startAnagram();
      else if (g.id === "pairs") startPairs();
      else startQuizGame();
    };
    strip.appendChild(b);
  });
}

// Пары на время: найди пары «слово — перевод»
let pairsCards = [], pairsOpen = [], pairsMatched = 0, pairsMoves = 0, pairsLock = false;

async function startPairs() {
  const data = await api(`/game/words/${gameLangId}?n=8`);
  const words = data.pairs;
  pairsCards = [];
  words.forEach((p, i) => {
    pairsCards.push({ key: i, text: p.word, kind: "word" });
    pairsCards.push({ key: i, text: p.translation, kind: "trans" });
  });
  pairsCards.sort(() => Math.random() - 0.5);
  pairsOpen = []; pairsMatched = 0; pairsMoves = 0; pairsLock = false;
  document.getElementById("pairs-moves").textContent = "0";
  const grid = document.getElementById("pairs-grid");
  grid.innerHTML = "";
  pairsCards.forEach((card, idx) => {
    const b = document.createElement("button");
    b.className = "pair-card";
    b.textContent = "?";
    b.onclick = () => flipPairCard(b, card, idx);
    grid.appendChild(b);
  });
  showScreen("screen-pairs");
}

function flipPairCard(btn, card, idx) {
  if (pairsLock || btn.classList.contains("open") || btn.classList.contains("matched")) return;
  btn.classList.add("open");
  btn.textContent = card.text;
  pairsOpen.push({ btn, card });
  if (pairsOpen.length === 2) {
    pairsMoves++;
    document.getElementById("pairs-moves").textContent = pairsMoves;
    pairsLock = true;
    const [a, b] = pairsOpen;
    const isMatch = a.card.key === b.card.key && a.card.kind !== b.card.kind;
    setTimeout(() => {
      if (isMatch) {
        a.btn.classList.replace("open", "matched");
        b.btn.classList.replace("open", "matched");
        pairsMatched += 2;
        if (pairsMatched === pairsCards.length) {
          const gained = Math.max(20 - pairsMoves, 5);
          api("/game/xp", "POST", { points: gained }).then(res => {
            showModal(t("pairs_found"),
              `${t("moves")}: <b>${pairsMoves}</b>. ${t("earned")}: <b>+${res.granted} XP</b>!`,
              "assets/pet_happy.svg");
            goHome();
          });
        }
      } else {
        a.btn.classList.remove("open"); a.btn.textContent = "?";
        b.btn.classList.remove("open"); b.btn.textContent = "?";
      }
      pairsOpen = [];
      pairsLock = false;
    }, isMatch ? 350 : 750);
  }
}

// Викторина: 10 вопросов, выбор перевода из 4
let qgWords = [], qgIdx = 0, qgScore = 0;

async function startQuizGame() {
  const data = await api(`/game/words/${gameLangId}?n=30`);
  qgWords = data.pairs.sort(() => Math.random() - 0.5).slice(0, 10);
  qgIdx = 0; qgScore = 0;
  showScreen("screen-quizgame");
  renderQgQuestion();
}

function renderQgQuestion() {
  const q = qgWords[qgIdx];
  document.getElementById("qg-progress").style.width = (qgIdx / qgWords.length * 100) + "%";
  document.getElementById("qg-step").textContent = `${t("quiz_step", {a: qgIdx + 1, b: qgWords.length})} · ${t("correct_cnt")}: ${qgScore}`;
  document.getElementById("qg-word").textContent = q.word;
  const opts = [q.translation];
  const others = qgWords.filter(w => w.translation !== q.translation);
  while (opts.length < 4 && others.length) {
    const c = others.splice(Math.floor(Math.random() * others.length), 1)[0].translation;
    if (!opts.includes(c)) opts.push(c);
  }
  const box = document.getElementById("qg-options");
  box.innerHTML = "";
  opts.sort(() => Math.random() - 0.5).forEach(opt => {
    const b = document.createElement("button");
    b.className = "card option";
    b.textContent = opt;
    b.onclick = () => {
      box.querySelectorAll(".option").forEach(x => {
        x.disabled = true;
        if (x.textContent === q.translation) x.classList.add("correct");
      });
      if (opt === q.translation) {
        qgScore++;
        setTimeout(nextQg, 400);
      } else {
        b.classList.add("wrong");
        setTimeout(nextQg, 1000);
      }
    };
    box.appendChild(b);
  });
}

function nextQg() {
  qgIdx++;
  if (qgIdx >= qgWords.length) {
    const gained = qgScore * 2;
    api("/game/xp", "POST", { points: gained }).then(res => {
      showModal(t("quiz_end"),
        `${t("correct_answers")}: <b>${qgScore}/${qgWords.length}</b>. ${t("earned")}: <b>+${res.granted} XP</b>!`,
        qgScore >= 7 ? "assets/pet_happy.svg" : "assets/logo.png");
      goHome();
    });
  } else {
    renderQgQuestion();
  }
}

// ---------- Смена ника ----------
async function editNickname() {
  const me = await api("/me");
  const name = await new Promise(resolve => {
    showModal("Твой ник", "");
    const modalText = document.getElementById("modal-text");
    modalText.innerHTML = "";
    const input = document.createElement("input");
    input.className = "dictation-input";
    input.value = me.first_name || "";
    input.maxLength = 32;
    modalText.appendChild(input);
    const btn = document.getElementById("modal-btn");
    btn.textContent = "Сохранить";
    confirmCb = () => resolve(input.value.trim());
    input.addEventListener("keydown", ev => { if (ev.key === "Enter") btn.click(); });
    setTimeout(() => input.focus(), 100);
  });
  if (!name) { showProfile(); return; }
  if (!isCleanText(name)) {
    showModal("Ой!", "Такой ник не подойдёт — попробуй другой.");
    return;
  }
  try {
    await api("/me", "PATCH", { nickname: name });
  } catch (e) {
    showModal("Ошибка", e.message);
    return;
  }
  showProfile();
}
