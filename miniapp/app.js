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
    tg.showAlert("Ошибка авторизации. Откройте приложение из Telegram.");
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
const chosenLangs = new Set();

async function loadOnboarding() {
  const langs = await api("/languages");
  const box = document.getElementById("lang-list");
  box.innerHTML = "";
  langs.forEach(l => {
    const btn = document.createElement("button");
    btn.className = "card";
    btn.innerHTML = `<b style="font-size:20px">${l.flag}</b> ${l.name}`;
    btn.onclick = () => {
      if (chosenLangs.has(l.id)) { chosenLangs.delete(l.id); btn.classList.remove("selected"); }
      else { chosenLangs.add(l.id); btn.classList.add("selected"); }
      document.getElementById("btn-start").disabled = chosenLangs.size === 0;
    };
    box.appendChild(btn);
  });
  document.getElementById("btn-start").onclick = async () => {
    for (const id of chosenLangs) await api("/languages", "POST", { language_id: id });
    goHome();
  };
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
         <div class="lc-sub">Нажми, чтобы начать урок</div></div>`;
    if (!item.completed) btn.onclick = () => startLesson(item.language_id);
    list.appendChild(btn);
  });
  showScreen("screen-home");
}

// ---------- Урок ----------
let lesson = null;
let exIndex = 0;
let selectedOption = null;
let correctCount = 0;

async function startLesson(languageId) {
  try {
    lesson = await api(`/lesson/${languageId}`);
  } catch (e) { if (e.message !== "limit") tg.showAlert("Не удалось загрузить урок"); return; }
  exIndex = 0;
  correctCount = 0;
  document.getElementById("lesson-title").textContent = lesson.title;
  showScreen("screen-lesson");
  renderExercise();
}

function renderExercise() {
  selectedOption = null;
  const ex = lesson.exercises[exIndex];
  document.getElementById("lesson-progress").style.width =
    (exIndex / lesson.exercises.length * 100) + "%";
  document.getElementById("exercise-box").innerHTML =
    `<p class="muted">${exIndex + 1} / ${lesson.exercises.length}</p><h2>${ex.prompt}</h2>`;

  const box = document.getElementById("exercise-options");
  box.innerHTML = "";
  const checkBtn = document.getElementById("btn-check");
  checkBtn.style.display = "";
  checkBtn.disabled = false;
  checkBtn.textContent = "Проверить";
  checkBtn.onclick = () => checkAnswer(ex);

  if (ex.type === "pairs") {
    renderPairs(ex, box);
    checkBtn.style.display = "none";
  } else if (ex.type === "sentence") {
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
      tg.showAlert(`Правильный ответ: ${correct}`);
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
    document.getElementById("lesson-progress").style.width = "100%";
    const result = await api(`/lesson/${lesson.lesson_id}/complete`, "POST");
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
  const [me, board, progress] = await Promise.all(
    [api("/me"), api("/leaderboard"), api("/progress")]);
  const lessonsDone = progress.items.filter(i => i.completed).length;
  document.getElementById("profile-name").textContent = me.first_name || "Ученик";
  document.getElementById("profile-sub").textContent = me.has_subscription
    ? `Подписка активна · ${me.subscription_days_left} дн.` : "Бесплатный аккаунт";
  document.getElementById("p-xp").textContent = me.xp;
  document.getElementById("p-streak").textContent = me.streak;
  document.getElementById("p-lessons").textContent = lessonsDone;
  document.getElementById("p-rank").textContent = board.my_rank;
  document.getElementById("btn-share").onclick = () => {
    const text = `Учу языки в Krolingo вместе с кенгуру! 🔥 Мой стрик: ${me.streak} дн.`;
    tg.openTelegramLink(
      `https://t.me/share/url?url=${encodeURIComponent("https://t.me/KrolingoBot")}&text=${encodeURIComponent(text)}`);
  };
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
      tg.showAlert("Отправили запрос боту — заверши покупку в чате с ботом.");
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
    if (e.message !== "limit" && e.message !== "auth") tg.showAlert("Ошибка загрузки");
  }
})();
