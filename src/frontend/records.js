const state = {
  log: {},
  selected: localDateKey(new Date()),
  calendarMonth: new Date(),
  lang: localStorage.getItem("gpm.lang") || ((navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en"),
};

const els = {
  todayStat: document.querySelector("#todayStat"),
  weekStat: document.querySelector("#weekStat"),
  monthStat: document.querySelector("#monthStat"),
  dayList: document.querySelector("#dayList"),
  heatmap: document.querySelector("#heatmap"),
  monthLabels: document.querySelector("#monthLabels"),
  selectedDate: document.querySelector("#selectedDate"),
  minutesOutput: document.querySelector("#minutesOutput"),
  noteInput: document.querySelector("#noteInput"),
  saveState: document.querySelector("#saveState"),
  langZhBtn: document.querySelector("#langZhBtn"),
  langEnBtn: document.querySelector("#langEnBtn"),
  todayBtn: document.querySelector("#todayBtn"),
  calendarBtn: document.querySelector("#calendarBtn"),
  calendarModal: document.querySelector("#calendarModal"),
  calendarTitle: document.querySelector("#calendarTitle"),
  calendarGrid: document.querySelector("#calendarGrid"),
  prevMonthBtn: document.querySelector("#prevMonthBtn"),
  nextMonthBtn: document.querySelector("#nextMonthBtn"),
};

let saveTimer = null;
let noteDirty = false;

const messages = {
  zh: {
    title: "练习记录",
    saved: "已保存",
    saving: "保存中",
    unsaved: "未保存",
    today: "今日",
    week: "本周",
    month: "本月",
    heatmap: "练习热力图",
    lastWeeks: "最近 26 周",
    recent: "最近记录",
    calendar: "日历",
    todayButton: "今天",
    selectedDate: "当前日期",
    duration: "时长",
    weekdaysShort: ["一", "二", "三", "四", "五", "六", "日"],
    monthLabel: (month) => `${month}月`,
    placeholder: "记录今天的电吉他练习内容：riff、节奏型、solo 段落、推弦/揉弦、扫拨、拨片控制、音色设置、速度训练等。",
  },
  en: {
    title: "Practice Log",
    saved: "Saved",
    saving: "Saving",
    unsaved: "Unsaved",
    today: "Today",
    week: "This Week",
    month: "This Month",
    heatmap: "Practice Heatmap",
    lastWeeks: "Last 26 weeks",
    recent: "Recent",
    calendar: "Calendar",
    todayButton: "Today",
    selectedDate: "Selected Date",
    duration: "Duration",
    weekdaysShort: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    monthLabel: (month) => `${month}`,
    placeholder: "Log today's electric guitar practice: riffs, rhythm parts, solo sections, bends/vibrato, sweep picking, picking control, tone settings, speed work, etc.",
  },
};

function t(key) {
  return messages[state.lang][key];
}

function applyLanguage() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-weekday]").forEach((element) => {
    element.textContent = t("weekdaysShort")[Number(element.dataset.weekday)];
  });
  document.querySelectorAll("[data-calendar-weekday]").forEach((element) => {
    element.textContent = t("weekdaysShort")[Number(element.dataset.calendarWeekday)];
  });
  els.noteInput.placeholder = t("placeholder");
  els.langZhBtn.classList.toggle("active", state.lang === "zh");
  els.langEnBtn.classList.toggle("active", state.lang === "en");
  if (els.saveState.textContent === messages.zh.saved || els.saveState.textContent === messages.en.saved) {
    els.saveState.textContent = t("saved");
  }
  renderHeatmap();
  renderCalendar();
}

function todayKey() {
  return localDateKey(new Date());
}

function localDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseDateKey(day) {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, month - 1, date);
}

function ensureDay(day) {
  if (!state.log[day]) {
    state.log[day] = { seconds: 0, note: "" };
  }
}

function secondsOf(entry) {
  if (!entry) return 0;
  if (typeof entry === "number") return entry;
  return Number(entry.seconds || 0);
}

function format(seconds) {
  seconds = Math.floor(seconds);
  const minutes = Math.floor(seconds / 60);
  const restSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m${String(restSeconds).padStart(2, "0")}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h${String(minutes % 60).padStart(2, "0")}m`;
}

function weekKey(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-${week}`;
}

function renderStats() {
  const now = new Date();
  let week = 0;
  let month = 0;
  for (const [day, entry] of Object.entries(state.log)) {
    const date = parseDateKey(day);
    const seconds = secondsOf(entry);
    if (weekKey(date) === weekKey(now)) week += seconds;
    if (date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth()) month += seconds;
  }
  els.todayStat.textContent = format(secondsOf(state.log[todayKey()]));
  els.weekStat.textContent = format(week);
  els.monthStat.textContent = format(month);
}

function levelFor(seconds) {
  const minutes = seconds / 60;
  if (minutes >= 120) return 4;
  if (minutes >= 60) return 3;
  if (minutes >= 25) return 2;
  if (minutes > 0) return 1;
  return 0;
}

function dateKey(date) {
  return localDateKey(date);
}

function addDays(date, days) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function startOfWeek(date) {
  const next = new Date(date);
  const day = next.getDay() || 7;
  next.setDate(next.getDate() - day + 1);
  next.setHours(0, 0, 0, 0);
  return next;
}

function renderHeatmap() {
  const today = new Date();
  const start = addDays(startOfWeek(today), -25 * 7);
  const cells = [];
  const labels = [];
  for (let week = 0; week < 26; week += 1) {
    const monday = addDays(start, week * 7);
    const previousMonday = addDays(start, (week - 1) * 7);
    const label = document.createElement("span");
    label.textContent = week === 0 || monday.getMonth() !== previousMonday.getMonth()
      ? t("monthLabel")(monday.getMonth() + 1)
      : "";
    labels.push(label);
    for (let day = 0; day < 7; day += 1) {
      const current = addDays(start, week * 7 + day);
      const key = dateKey(current);
      const level = levelFor(secondsOf(state.log[key]));
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = `heat-cell level-${level}`;
      cell.title = `${key} ${format(secondsOf(state.log[key]))}`;
      cell.addEventListener("click", () => selectDay(key));
      cells.push(cell);
    }
  }
  els.monthLabels.replaceChildren(...labels);
  els.heatmap.replaceChildren(...cells);
}

function renderDays() {
  ensureDay(todayKey());
  const days = Object.keys(state.log)
    .filter((day) => secondsOf(state.log[day]) > 0 || day === todayKey() || state.log[day]?.note)
    .sort()
    .reverse()
    .slice(0, 45);
  els.dayList.replaceChildren(
    ...days.map((day) => {
      const button = document.createElement("button");
      button.className = `day-item${day === state.selected ? " active" : ""}`;
      button.type = "button";
      button.innerHTML = `<strong>${day}</strong><span>${format(secondsOf(state.log[day]))}</span>`;
      button.addEventListener("click", () => selectDay(day));
      return button;
    }),
  );
}

function renderCalendar() {
  const month = state.calendarMonth;
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  els.calendarTitle.textContent = state.lang === "zh"
    ? `${year}年 ${monthIndex + 1}月`
    : `${year}-${String(monthIndex + 1).padStart(2, "0")}`;

  const first = new Date(year, monthIndex, 1);
  const start = addDays(first, -((first.getDay() || 7) - 1));
  const cells = [];
  for (let i = 0; i < 42; i += 1) {
    const current = addDays(start, i);
    const key = dateKey(current);
    const seconds = secondsOf(state.log[key]);
    const level = levelFor(seconds);
    const hasPractice = seconds > 0 || key === todayKey();
    const button = document.createElement("button");
    button.type = "button";
    button.className = `calendar-day level-${level}${current.getMonth() !== monthIndex ? " outside" : ""}${key === state.selected ? " active" : ""}${hasPractice ? " practiced" : " empty"}`;
    button.innerHTML = `<span>${current.getDate()}</span><i class="dot level-${level}"></i>`;
    button.title = `${key} ${format(seconds)}`;
    button.disabled = !hasPractice;
    if (hasPractice) {
      button.addEventListener("click", () => {
        selectDay(key);
        els.calendarModal.hidden = true;
      });
    }
    cells.push(button);
  }
  els.calendarGrid.replaceChildren(...cells);
}

function selectDay(day, shouldSaveCurrent = true) {
  if (shouldSaveCurrent) {
    saveLocal();
  }
  state.selected = day;
  ensureDay(day);
  const entry = state.log[day];
  els.selectedDate.textContent = day;
  els.minutesOutput.textContent = format(secondsOf(entry));
  els.noteInput.value = entry.note || "";
  renderDays();
  renderCalendar();
  renderHeatmap();
}

function saveLocal() {
  ensureDay(state.selected);
  const currentSeconds = secondsOf(state.log[state.selected]);
  state.log[state.selected] = {
    seconds: currentSeconds,
    note: els.noteInput.value.trim(),
  };
}

async function saveRemote() {
  saveLocal();
  els.saveState.textContent = t("saving");
  const response = await fetch("/api/log", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.log),
  });
  state.log = await response.json();
  noteDirty = false;
  els.saveState.textContent = t("saved");
  renderStats();
  renderDays();
  renderCalendar();
  renderHeatmap();
}

function scheduleSave() {
  noteDirty = true;
  saveLocal();
  els.saveState.textContent = t("unsaved");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveRemote, 500);
}

async function refreshRemote() {
  const response = await fetch("/api/log");
  const latest = await response.json();
  const draftNote = noteDirty ? els.noteInput.value : null;
  state.log = latest;
  ensureDay(state.selected);
  els.minutesOutput.textContent = format(secondsOf(state.log[state.selected]));
  if (draftNote !== null) {
    els.noteInput.value = draftNote;
    saveLocal();
  } else {
    els.noteInput.value = state.log[state.selected]?.note || "";
  }
  renderStats();
  renderDays();
  renderHeatmap();
  renderCalendar();
}

async function load() {
  const response = await fetch("/api/log");
  state.log = await response.json();
  ensureDay(todayKey());
  selectDay(state.selected, false);
  renderStats();
  renderDays();
  renderHeatmap();
  renderCalendar();
}

els.todayBtn.addEventListener("click", () => selectDay(todayKey()));
els.calendarBtn.addEventListener("click", () => {
  state.calendarMonth = parseDateKey(state.selected);
  renderCalendar();
  els.calendarModal.hidden = false;
});
els.calendarModal.addEventListener("click", (event) => {
  if (event.target === els.calendarModal) {
    els.calendarModal.hidden = true;
  }
});
els.prevMonthBtn.addEventListener("click", () => {
  state.calendarMonth = new Date(state.calendarMonth.getFullYear(), state.calendarMonth.getMonth() - 1, 1);
  renderCalendar();
});
els.nextMonthBtn.addEventListener("click", () => {
  state.calendarMonth = new Date(state.calendarMonth.getFullYear(), state.calendarMonth.getMonth() + 1, 1);
  renderCalendar();
});
function setLanguage(lang) {
  state.lang = lang;
  localStorage.setItem("gpm.lang", state.lang);
  applyLanguage();
}

els.langZhBtn.addEventListener("click", () => setLanguage("zh"));
els.langEnBtn.addEventListener("click", () => setLanguage("en"));
els.noteInput.addEventListener("input", scheduleSave);

applyLanguage();
load();
setInterval(refreshRemote, 1000);
