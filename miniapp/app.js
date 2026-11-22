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
  if (!res.ok) throw new Error(await res.text());
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
  if (me.has_subscription) {
    document.getElementById("onboarding-hint").textContent =
      "С подпиской можно учить несколько языков. Выбери один, потом добавишь ещё.";
  }
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
      `Как хорошо ты знаешь: ${chosenLangName}?`;
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
      `${res.level} · ${res.level_name}`;
    showScreen("screen-level-result");
  } else {
    renderQuizQuestion();
  }
}

// ---------- Главная ----------
async function goHome() {
  showScreen("screen-loading");
  const [me, progress] = await Promise.all([api("/me"), api("/progress")]);
  document.getElementById("streak").textContent = me.streak;
  document.getElementById("xp").textContent = me.xp;
  document.getElementById("hello-name").textContent =
    (me.first_name ? me.first_name + ", п" : "П") + "родолжим учиться?";
  document.getElementById("limit-info").textContent = me.has_subscription
    ? `Подписка активна · осталось ${me.subscription_days_left} дн.`
    : `Сегодня: ${progress.lessons_done_today} из ${progress.free_daily_limit} бесплатных уроков`;

  const list = document.getElementById("progress-list");
  list.innerHTML = "";
  if (progress.items.length === 0) {
    await loadOnboarding();
    showScreen("screen-onboarding");
    return;
  }
  progress.items.forEach(item => {
    const btn = document.createElement("button");
    btn.className = "lesson-card" + (item.completed ? " completed" : "");
    btn.innerHTML = item.completed
      ? `<div class="lc-icon"><svg class="ic"><use href="#i-crown"/></svg></div>
         <div><div class="lc-title">Все уроки пройдены</div>
         <div class="lc-sub">Ты молодец! Скоро добавим ещё</div></div>`
      : `<div class="lc-icon"><svg class="ic"><use href="#i-play"/></svg></div>
         <div><div class="lc-title">${item.lesson_title}</div>
         <div class="lc-sub">${item.language_name} · уровень ${item.level} (${item.level_name})</div></div>`;
    if (!item.completed) btn.onclick = () => startLesson(item.language_id);
    list.appendChild(btn);
  });
  if (me.has_subscription) {
    const add = document.createElement("button");
    add.className = "card";
    add.innerHTML = `<b>+ Добавить язык</b>`;
    add.onclick = async () => { await loadOnboarding(); showScreen("screen-onboarding"); };
    list.appendChild(add);
  }
  showScreen("screen-home");
}

// ---------- Урок ----------
let lesson = null;
let exIndex = 0;
let selectedOption = null;
let correctCount = 0;
let retryQueue = [];      // задания, где нажали «Не знаю»
let retryRound = false;

async function startLesson(languageId) {
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
  document.getElementById("lesson-title").textContent = lesson.title;
  showScreen("screen-lesson");
  renderExercise();
}

function renderExercise() {
  selectedOption = null;
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
  checkBtn.textContent = "Проверить";
  checkBtn.onclick = () => checkAnswer(ex);

  const dontKnowBtn = document.getElementById("btn-dontknow");
  if (ex.type === "pairs") {
    dontKnowBtn.style.display = "none";
    renderPairs(ex, box);
    checkBtn.style.display = "none";
  } else {
    dontKnowBtn.style.display = "";
    dontKnowBtn.textContent = "Не знаю";
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
  const box = document.getElementById("exercise-options");
  box.querySelectorAll(".option").forEach(b => {
    b.disabled = true;
    if (b.textContent === ex.payload.correct) b.classList.add("correct");
  });
  const line = document.getElementById("sentence-line");
  if (line) line.classList.add("revealed");
  if (!retryRound) retryQueue.push(ex);
  const checkBtn = document.getElementById("btn-check");
  checkBtn.textContent = "Дальше";
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

function checkAnswer(ex) {
  if (ex.type === "sentence") {
    selectedOption = getSentenceAnswer();
    if (!selectedOption) return;
  }
  if (selectedOption === null || selectedOption === undefined) return;

  const correct = ex.payload.correct;
  const ok = ex.type === "sentence"
    ? selectedOption.trim().toLowerCase() === correct.trim().toLowerCase()
    : selectedOption === correct;

  const box = document.getElementById("exercise-options");
  box.querySelectorAll(".option").forEach(b => {
    if (b.textContent === correct) b.classList.add("correct");
  });

  const checkBtn = document.getElementById("btn-check");
  if (!ok) {
    if (ex.type === "sentence") {
      showModal("Правильный ответ", `«${correct}»`);
      nextExercise();
      return;
    }
    box.querySelectorAll(".option").forEach(b => {
      if (b.textContent === selectedOption) b.classList.add("wrong");
    });
    checkBtn.textContent = "Дальше";
    checkBtn.onclick = nextExercise;
  } else {
    correctCount++;
    nextExercise();
  }
}

async function nextExercise() {
  exIndex++;
  document.getElementById("btn-check").textContent = "Проверить";
  if (exIndex >= lesson.exercises.length) {
    if (!retryRound && retryQueue.length) {
      // второй круг: прогоняем задания, где было «Не знаю»
      retryRound = true;
      lesson = { ...lesson, exercises: retryQueue };
      exIndex = 0;
      showModal("Время повторить", "Сейчас ещё раз покажем задания, где был выбран «Не знаю».");
      renderExercise();
      return;
    }
    document.getElementById("lesson-progress").style.width = "100%";
    const result = await api(`/lesson/${lesson.lesson_id}/complete`, "POST");
    if (result.gift) {
      setTimeout(() => showModal("Подарок от Krolingo!",
        "Ты занимаешься уже ${result.streak} дней подряд! Лови <b>+1 бонусный урок</b> на сегодня.",
        "assets/pet_happy.svg"), 400);
    } else if (result.level && !lesson.repeat && result.level !== lesson.level) {
      setTimeout(() => showModal("Новый уровень!",
        `Ты перешёл на уровень <b>${result.level}</b>! Уроки станут интереснее.`, "assets/pet_happy.svg"), 400);
    }
    document.getElementById("res-correct").textContent =
      `${correctCount}/${lesson.exercises.length}`;
    document.getElementById("res-streak").textContent = result.streak;
    document.getElementById("res-xp").textContent = result.xp;
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
      <div class="board-name">${item.name}${item.is_me ? " (ты)" : ""}</div>
      <div class="board-xp">${item.xp}<svg class="ic gem" style="width:16px;height:16px"><use href="#i-gem"/></svg></div>`;
    list.appendChild(row);
  });
  showScreen("screen-board");
}

// ---------- Профиль ----------
async function showProfile() {
  showScreen("screen-loading");
  const [me, board, progress, history] = await Promise.all(
    [api("/me"), api("/leaderboard"), api("/progress"), api("/history")]);
  const happy = me.pet_mood === "happy";
  document.querySelector(".avatar-ring img").src =
    happy ? "assets/pet_happy.svg" : "assets/pet_sad.svg";
  document.getElementById("pet-caption").textContent = happy
    ? (me.lessons_done_today > 0 ? "Кенгу доволен: ты сегодня занимался!" : "Кенгу рад тебя видеть!")
    : "Кенгу скучает… пройди урок, чтобы он повеселел!";
  const lessonsDone = progress.items.filter(i => i.completed).length;
  document.getElementById("profile-name").textContent = me.first_name || "Ученик";
  document.getElementById("profile-sub").textContent = me.has_subscription
    ? `Подписка активна · ${me.subscription_days_left} дн.` : "Бесплатный аккаунт";
  document.getElementById("p-xp").textContent = me.xp;
  document.getElementById("p-streak").textContent = me.streak;
  document.getElementById("p-lessons").textContent =
    progress.items.length ? lessonsDone : (history.items.length || 0);
  document.getElementById("p-rank").textContent = board.my_rank;
  document.getElementById("btn-share").onclick = () => {
    const text = `Учу языки в Krolingo вместе с кенгуру! Мой стрик: ${me.streak} дн.`;
    tg.openTelegramLink(
      `https://t.me/share/url?url=${encodeURIComponent("https://t.me/KrolingoBot")}&text=${encodeURIComponent(text)}`);
  };
  const hlist = document.getElementById("history-list");
  hlist.innerHTML = "";
  if (!history.items.length) {
    hlist.innerHTML = `<p class="muted">Пока нет пройденных уроков</p>`;
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
async function showPlans() {
  showScreen("screen-loading");
  const plans = await api("/plans");
  const list = document.getElementById("plans-list");
  list.innerHTML = "";
  plans.forEach(p => {
    const btn = document.createElement("button");
    btn.className = "card";
    btn.innerHTML = `<svg class="ic"><use href="#i-star"/></svg>
      <div style="flex:1"><b>${p.title}</b><br>
      <span class="muted" style="margin:0">Безлимитные уроки на ${p.days} дней</span></div>
      <b style="color:var(--gold)">${p.stars}⭐</b>`;
    btn.onclick = () => {
      tg.sendData(JSON.stringify({ action: "buy_plan", plan: p.key }));
      showModal("Запрос отправлен", "Заверши покупку в чате с ботом — там появится инвойс Telegram Stars.");
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
