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
    showError("Ошибка авторизации. Откройте приложение из Telegram.");
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
}

function showError(msg) {
  tg.showAlert(msg);
}

// ---------- Онбординг ----------
const chosenLangs = new Set();

async function loadOnboarding() {
  const langs = await api("/languages");
  const box = document.getElementById("lang-list");
  box.innerHTML = "";
  langs.forEach(l => {
    const btn = document.createElement("button");
    btn.className = "card";
    btn.textContent = `${l.flag} ${l.name}`;
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

// ---------- Главный экран ----------
async function goHome() {
  showScreen("screen-loading");
  const [me, progress] = await Promise.all([api("/me"), api("/progress")]);
  document.getElementById("streak").textContent = "🔥 " + me.streak;
  document.getElementById("xp").textContent = "✨ " + me.xp;
  document.getElementById("limit-info").textContent = me.has_subscription
    ? `⭐ Подписка активна (осталось ${me.subscription_days_left} дн.)`
    : `Сегодня пройдено ${progress.lessons_done_today} из ${progress.free_daily_limit} бесплатных уроков`;

  const list = document.getElementById("progress-list");
  list.innerHTML = "";
  progress.items.forEach(item => {
    const btn = document.createElement("button");
    btn.className = "card" + (item.completed ? " done" : "");
    btn.innerHTML = item.completed
      ? `✅ Уроки пройдены`
      : `<b>${item.lesson_title}</b><br><span class="muted">Нажми, чтобы начать →</span>`;
    btn.onclick = () => startLesson(item.language_id);
    list.appendChild(btn);
  });

  if (progress.items.length === 0) {
    showScreen("screen-onboarding");
    return;
  }
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
  } catch (e) { if (e.message !== "limit") showError("Не удалось загрузить урок"); return; }
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
  document.getElementById("exercise-box").innerHTML = `<p class="muted">${exIndex + 1}/${lesson.exercises.length}</p><h2>${ex.prompt}</h2>`;

  const box = document.getElementById("exercise-options");
  box.innerHTML = "";

  if (ex.type === "pairs") {
    const flat = ex.payload.pairs.flat().sort(() => Math.random() - 0.5);
    let first = null, matched = 0;
    flat.forEach(word => {
      const btn = document.createElement("button");
      btn.className = "card";
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
    document.getElementById("btn-check").style.display = "none";
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
    const checkBtn = document.getElementById("btn-check");
    checkBtn.style.display = "";
    checkBtn.disabled = false;
    checkBtn.onclick = () => checkAnswer(ex);
  }
}

function checkAnswer(ex) {
  if (selectedOption === null) return;
  const ok = selectedOption === ex.payload.correct;
  const box = document.getElementById("exercise-options");
  box.querySelectorAll(".option").forEach(b => {
    if (b.textContent === ex.payload.correct) b.classList.add("correct");
  });
  if (!ok) {
    box.querySelectorAll(".option").forEach(b => {
      if (b.textContent === selectedOption) b.classList.add("wrong");
    });
    document.getElementById("btn-check").textContent = "Дальше";
    document.getElementById("btn-check").onclick = nextExercise;
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
    document.getElementById("result-stats").textContent =
      `Верных ответов: ${correctCount}/${lesson.exercises.length} · 🔥 ${result.streak} · ✨ ${result.xp} XP`;
    showScreen("screen-result");
  } else {
    renderExercise();
  }
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
    btn.innerHTML = `<b>${p.title}</b><br><span class="muted">⭐ ${p.stars}</span>`;
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
    if (e.message !== "limit" && e.message !== "auth") showError("Ошибка загрузки");
  }
})();
