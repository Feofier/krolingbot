import io

s = io.open('miniapp/app.js', encoding='utf-8').read()

# ============ 1) Диктант: рендер + ввод + кнопка прослушки ============
s = s.replace('''  if (ex.type === "pairs") {
    dontKnowBtn.style.display = "none";
    renderPairs(ex, box);
    checkBtn.style.display = "none";
  } else {''',
'''  if (ex.type === "pairs") {
    dontKnowBtn.style.display = "none";
    renderPairs(ex, box);
    checkBtn.style.display = "none";
  } else if (ex.type === "dictation") {
    renderDictation(ex, box, checkBtn);
  } else {''')

dictation_fn = '''
// Диктант: слушаешь слово и вписываешь его
const BAD_WORDS = ["fuck","shit","bitch","хуй","пизд","еба","сука","бляд","kurwa","puta","merde"];
function isCleanText(t) {
  const low = t.toLowerCase();
  return !BAD_WORDS.some(w => low.includes(w));
}

function renderDictation(ex, box, checkBtn) {
  const dontKnowBtn = document.getElementById("btn-dontknow");
  dontKnowBtn.style.display = "";
  // убираем подсказку-перевод из текста задания
  const cleanPrompt = ex.prompt.replace(/\\s*\\([^)]*\\)\\s*$/, "");
  document.querySelector("#exercise-box h2").textContent = cleanPrompt;

  const row = document.createElement("div");
  row.className = "dictation-row";
  const replay = document.createElement("button");
  replay.className = "btn btn-blue dictation-play";
  replay.innerHTML = `<svg class="ic"><use href="#i-sound"/></svg> ${t("listen")}`;
  replay.onclick = () => speak(ex.payload.word, 0.72);
  const input = document.createElement("input");
  input.className = "dictation-input";
  input.placeholder = t("write_heard");
  input.autocapitalize = "none";
  input.autocomplete = "off";
  input.addEventListener("keydown", ev => {
    if (ev.key === "Enter" && input.value.trim()) checkBtn.click();
  });
  row.appendChild(replay);
  row.appendChild(input);
  box.appendChild(row);
  setTimeout(() => { input.focus(); }, 400);
  // автопроигрывание дважды: сразу и повтор через паузу
  setTimeout(() => speak(ex.payload.word, 0.72), 500);
  setTimeout(() => speak(ex.payload.word, 0.72), 2400);

  selectedOption = null;
  checkBtn.onclick = () => {
    const val = input.value.trim();
    if (!val) return;
    if (!isCleanText(val)) {
      showModal("Ой!", "Такие слова мы не изучаем. Попробуй другое!");
      input.value = "";
      return;
    }
    selectedOption = val;
    checkAnswer(ex);
  };
}
'''
s = s.replace('// Сборка предложения из слов', dictation_fn + '\n// Сборка предложения из слов')

# ============ 2) Спринт: блокировка после конца ============
s = s.replace('''function sprintAnswer(saidTrue) {
  if (saidTrue === sprintCurrentTrue) {''',
'''let sprintOver = false;

function sprintAnswer(saidTrue) {
  if (sprintOver) return;
  if (saidTrue === sprintCurrentTrue) {''')
s = s.replace('''async function endSprint() {
  clearInterval(sprintTimer);''',
'''async function endSprint() {
  if (sprintOver) return;
  sprintOver = true;
  clearInterval(sprintTimer);''')
s = s.replace('''async function startSprint() {
  const data = await api(`/game/words/${gameLangId}?n=40`);''',
'''async function startSprint() {
  sprintOver = false;
  const data = await api(`/game/words/${gameLangId}?n=40`);''')

# ============ 3) Голоса на выбор в настройках ============
s = s.replace('''function pickVoice(lang) {
  const base = lang.split("-")[0];
  const opts = voicesCache.filter(v => v.lang.replace("_", "-").toLowerCase().startsWith(base));
  return opts.find(v => /google|natural|neural|online/i.test(v.name))
      || opts.find(v => /samantha|zira|aria|susan|female|milena|allison/i.test(v.name))
      || opts[0] || null;
}''',
'''function pickVoice(lang) {
  const base = lang.split("-")[0];
  const opts = voicesCache.filter(v => v.lang.replace("_", "-").toLowerCase().startsWith(base));
  // выбранный пользователем голос (если доступен для этого языка)
  const saved = localStorage.getItem("tts_voice");
  if (saved) {
    const v = opts.find(v => v.voiceURI === saved);
    if (v) return v;
  }
  return opts.find(v => /google|natural|neural|online/i.test(v.name))
      || opts.find(v => /samantha|zira|aria|susan|female|milena|allison/i.test(v.name))
      || opts[0] || null;
}

async function showVoices() {
  showScreen("screen-loading");
  // дожидаемся загрузки списка голосов
  if (!voicesCache.length && window.speechSynthesis) {
    await new Promise(res => {
      loadVoices();
      if (voicesCache.length) return res();
      speechSynthesis.onvoiceschanged = () => { loadVoices(); res(); };
      setTimeout(res, 2000);
    });
  }
  const list = document.getElementById("voice-list");
  list.innerHTML = "";
  const current = localStorage.getItem("tts_voice");
  // группируем по языку изучения в первую очередь
  const base = ({en:"en", es:"es", de:"de", fr:"fr", it:"it", pt:"pt",
                 tr:"tr", pl:"pl", uk:"uk", ja:"ja"})[lessonLangCode] || "en";
  const sorted = [...voicesCache].sort((a, b) =>
    (b.lang.startsWith(base) ? 1 : 0) - (a.lang.startsWith(base) ? 1 : 0));
  if (!sorted.length) {
    list.innerHTML = `<p class="muted">${t("voices_empty")}</p>`;
  }
  sorted.slice(0, 40).forEach(v => {
    const b = document.createElement("button");
    b.className = "card" + (v.voiceURI === current ? " selected" : "");
    b.innerHTML = `<div style="flex:1"><b>${v.name}</b><br>
      <span class="muted" style="margin:0">${v.lang}</span></div>
      <svg class="ic"><use href="#i-sound"/></svg>`;
    b.onclick = () => {
      localStorage.setItem("tts_voice", v.voiceURI);
      speak("Hello! Привет! Hola!", 0.8);
      showVoices();
    };
    list.appendChild(b);
  });
  showScreen("screen-voice");
}

document.getElementById("btn-voice").onclick = showVoices;
'''

io.open('miniapp/app.js', 'w', encoding='utf-8').write(s)
print('app.js ok')
