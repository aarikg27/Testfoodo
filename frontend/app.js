const API_BASE = (window.TESTFOODO_CONFIG?.API_BASE_URL || "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");
const STORAGE = {
  token: "testfoodo.session",
  goals: "testfoodo.guest.goals",
  preferences: "testfoodo.guest.preferences",
  logs: "testfoodo.guest.logs",
  favorites: "testfoodo.guest.favorites",
  meals: "testfoodo.guest.savedMeals",
  hall: "testfoodo.lastHall",
};

const DEFAULT_GOALS = {
  calorie_goal: 2200,
  protein_goal_g: 140,
  carbs_goal_g: 250,
  fat_goal_g: 70,
};
const DEFAULT_PREFERENCES = {
  dietary_preferences: [],
  excluded_labels: [],
  favorite_hall_id: null,
  profile: {
    age: null,
    height_cm: null,
    weight_kg: null,
    gender: null,
    activity_level: "moderate",
    goal_type: "maintain",
    use_profile_targets: true,
  },
};
const EXCLUSION_LABELS = [
  "alcohol",
  "coconut",
  "dairy",
  "eggs",
  "fish",
  "gluten",
  "nuts",
  "pea_protein",
  "pork",
  "sesame",
  "shellfish",
  "soy",
];

const state = {
  token: localStorage.getItem(STORAGE.token),
  user: null,
  date: localDateString(new Date()),
  hall: localStorage.getItem(STORAGE.hall) || "",
  station: "",
  meal: currentMeal(),
  search: "",
  halls: [],
  stations: [],
  menu: [],
  menuTotal: 0,
  lastScrapedAt: null,
  menuContext: null,
  refreshPoll: null,
  visibleCount: 12,
  goals: { ...DEFAULT_GOALS },
  preferences: { ...DEFAULT_PREFERENCES },
  logs: [],
  historyLogs: [],
  favorites: [],
  savedMeals: [],
  recommendations: [],
  authMode: "login",
};

const elements = {
  date: document.querySelector("#date-filter"),
  hall: document.querySelector("#hall-filter"),
  station: document.querySelector("#station-filter"),
  todayLabel: document.querySelector("#today-label"),
  freshness: document.querySelector("#freshness-status"),
  macroGrid: document.querySelector("#macro-grid"),
  nutritionGuidance: document.querySelector("#nutrition-guidance"),
  foodGrid: document.querySelector("#food-grid"),
  resultCount: document.querySelector("#result-count"),
  search: document.querySelector("#food-search"),
  activeFilters: document.querySelector("#active-filters"),
  loadMore: document.querySelector("#load-more-button"),
  logList: document.querySelector("#log-list"),
  logEmpty: document.querySelector("#log-empty"),
  logTotals: document.querySelector("#log-totals"),
  logCount: document.querySelector("#log-count"),
  recommendationGrid: document.querySelector("#recommendation-grid"),
  favoritesList: document.querySelector("#favorites-list"),
  savedMealsList: document.querySelector("#saved-meals-list"),
  historyChart: document.querySelector("#history-chart"),
  weeklyAverage: document.querySelector("#weekly-average"),
  profileName: document.querySelector("#profile-name"),
  profileSubtitle: document.querySelector("#profile-subtitle"),
  profileAvatar: document.querySelector("#profile-avatar"),
  toastRegion: document.querySelector("#toast-region"),
  menuDateTitle: document.querySelector("#menu-date-title"),
  targetPreview: document.querySelector("#target-preview"),
};

function localDateString(value) {
  const offset = value.getTimezoneOffset();
  return new Date(value.getTime() - offset * 60000).toISOString().slice(0, 10);
}

function apiDateTime(value) {
  if (typeof value !== "string") return new Date(value);
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

function dateWithOffset(days) {
  const value = new Date(`${state.menuContext?.today || state.date}T12:00:00`);
  value.setDate(value.getDate() + days);
  return localDateString(value);
}

function currentMeal() {
  const hour = Number(
    new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      hour12: false,
      timeZone: "America/New_York",
    }).format(new Date()),
  );
  return hour < 11 ? "Breakfast" : hour < 16 ? "Lunch" : "Dinner";
}

function isTodaySelected() {
  return state.date === (state.menuContext?.today || localDateString(new Date()));
}

function selectedDateContext() {
  return state.menuContext?.dates?.find((item) => item.date === state.date) || null;
}

function allowedMeals() {
  if (isTodaySelected()) return [state.menuContext?.current_meal || currentMeal()];
  return selectedDateContext()?.meal_periods || [];
}

function syncSelectedMeal() {
  const meals = allowedMeals();
  if (meals.length && !meals.includes(state.meal)) state.meal = meals[0];
}

function selectedDateTime() {
  const now = new Date();
  const localTime = now.toTimeString().slice(0, 8);
  return new Date(`${state.date}T${localTime}`).toISOString();
}

function readStorage(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value ?? fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function escapeHTML(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function labelText(value) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNumber(value, decimals = 0) {
  return Number(value || 0).toLocaleString(undefined, {
    maximumFractionDigits: decimals,
  });
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

function portionGuidance(name, servingSize, servings = 1) {
  const size = String(servingSize || "").trim();
  const count = Number(servings || 1);
  const lowerName = String(name || "").toLowerCase();
  const ounceMatch = size.match(/([0-9]+(?:\.[0-9]+)?)\s*oz/i);
  if (ounceMatch) {
    const ounces = Number(ounceMatch[1]) * count;
    if (/soup|chili|stew|beverage|milk|juice/.test(lowerName)) {
      const cups = ounces / 8;
      return `${formatNumber(ounces, 1)} oz — about ${formatNumber(cups, 1)} cup${Math.abs(cups - 1) < 0.05 ? "" : "s"}`;
    }
    if (/chip|cracker|pretzel|popcorn/.test(lowerName)) {
      const handfuls = ounces / 2;
      return `${formatNumber(ounces, 1)} oz — about ${formatNumber(handfuls, 1)} loose handful${Math.abs(handfuls - 1) < 0.05 ? "" : "s"}`;
    }
    if (/chicken|turkey|beef|pork|salmon|fish|steak|tofu|tempeh/.test(lowerName)) {
      const palms = ounces / 4;
      return `${formatNumber(ounces, 1)} oz — about ${formatNumber(palms, 1)} palm-size portion${Math.abs(palms - 1) < 0.05 ? "" : "s"}`;
    }
    if (ounces <= 2) {
      const tablespoons = ounces * 2;
      return `${formatNumber(ounces, 1)} oz — about ${formatNumber(tablespoons, 1)} tablespoon${Math.abs(tablespoons - 1) < 0.05 ? "" : "s"}`;
    }
    const scoops = ounces / 4;
    return `${formatNumber(ounces, 1)} oz — about ${formatNumber(scoops, 1)} level serving-spoon scoop${Math.abs(scoops - 1) < 0.05 ? "" : "s"}`;
  }
  const cupMatch = size.match(/([0-9]+(?:\.[0-9]+)?|1\/2|1\/4|3\/4)\s*cups?/i);
  if (cupMatch) {
    const fractions = { "1/2": 0.5, "1/4": 0.25, "3/4": 0.75 };
    const cups = (fractions[cupMatch[1]] || Number(cupMatch[1])) * count;
    return `${formatNumber(cups, 2)} cup${Math.abs(cups - 1) < 0.05 ? "" : "s"} — roughly ${formatNumber(cups * 2, 1)} level scoop${Math.abs(cups * 2 - 1) < 0.05 ? "" : "s"}`;
  }
  const pieceMatch = size.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:ea|each|pieces?|slices?|patt(?:y|ies)|links?|fillets?)/i);
  if (pieceMatch) {
    const pieces = Number(pieceMatch[1]) * count;
    return `${formatNumber(pieces, 1)} piece${Math.abs(pieces - 1) < 0.05 ? "" : "s"}`;
  }
  return `${formatNumber(count, 1)} × ${size || "UMD serving"}`;
}

function profileFromForm() {
  const feet = Number(document.querySelector("#profile-height-ft").value || 0);
  const inches = Number(document.querySelector("#profile-height-in").value || 0);
  const pounds = Number(document.querySelector("#profile-weight").value || 0);
  return {
    age: Number(document.querySelector("#profile-age").value) || null,
    height_cm: feet || inches ? Number(((feet * 12 + inches) * 2.54).toFixed(1)) : null,
    weight_kg: pounds ? Number((pounds / 2.20462).toFixed(1)) : null,
    gender: document.querySelector("#profile-gender").value || null,
    activity_level: document.querySelector("#profile-activity").value,
    goal_type: document.querySelector("#profile-goal").value,
    use_profile_targets: document.querySelector("#profile-use-targets").checked,
  };
}

function suggestedGoals(profile) {
  if (!profile.age || !profile.height_cm || !profile.weight_kg) return null;
  const genderAdjustment = profile.gender === "man" ? 5 : profile.gender === "woman" ? -161 : -78;
  const activityFactors = { sedentary: 1.2, light: 1.375, moderate: 1.55, very_active: 1.725 };
  const goalAdjustments = { lose: -300, maintain: 0, gain: 300 };
  const bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age + genderAdjustment;
  const calories = Math.round(Math.min(5000, Math.max(1200, bmr * (activityFactors[profile.activity_level] || 1.55) + (goalAdjustments[profile.goal_type] || 0))) / 25) * 25;
  const proteinMultiplier = profile.goal_type === "lose" ? 1.8 : profile.goal_type === "gain" ? 1.7 : 1.6;
  const protein = Math.round(profile.weight_kg * proteinMultiplier);
  const fat = Math.round((calories * 0.27) / 9);
  const carbs = Math.max(50, Math.round((calories - protein * 4 - fat * 9) / 4));
  return { calorie_goal: calories, protein_goal_g: protein, carbs_goal_g: carbs, fat_goal_g: fat };
}

function renderTargetPreview() {
  const goals = suggestedGoals(profileFromForm());
  elements.targetPreview.classList.toggle("ready", Boolean(goals));
  elements.targetPreview.textContent = goals
    ? `Estimated daily targets: ${formatNumber(goals.calorie_goal)} kcal · ${formatNumber(goals.protein_goal_g)}g protein · ${formatNumber(goals.carbs_goal_g)}g carbs · ${formatNumber(goals.fat_goal_g)}g fat. This is a planning estimate, not medical advice.`
    : "Complete age, height, and weight to preview your estimated targets.";
  return goals;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (response.status === 401 && state.token) {
    clearSession();
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : detail;
    } catch {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function clearSession() {
  state.token = null;
  state.user = null;
  localStorage.removeItem(STORAGE.token);
  renderProfile();
}

function toast(message) {
  const item = document.createElement("div");
  item.className = "toast";
  item.textContent = message;
  elements.toastRegion.append(item);
  setTimeout(() => item.remove(), 3400);
}

function totalsFor(logs = state.logs) {
  return logs.reduce(
    (totals, log) => {
      totals.calories += Number(log.calories_per_serving || 0) * Number(log.servings || 1);
      totals.protein_g += Number(log.protein_per_serving_g || 0) * Number(log.servings || 1);
      totals.carbs_g += Number(log.carbs_per_serving_g || 0) * Number(log.servings || 1);
      totals.fat_g += Number(log.fat_per_serving_g || 0) * Number(log.servings || 1);
      return totals;
    },
    { calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0 },
  );
}

function remainingMacros() {
  const totals = totalsFor();
  return {
    calories: Math.max(state.goals.calorie_goal - totals.calories, 0),
    protein_g: Math.max(state.goals.protein_goal_g - totals.protein_g, 0),
    carbs_g: Math.max(state.goals.carbs_goal_g - totals.carbs_g, 0),
    fat_g: Math.max(state.goals.fat_goal_g - totals.fat_g, 0),
  };
}

function renderProfile() {
  if (state.user) {
    elements.profileName.textContent = state.user.display_name;
    elements.profileSubtitle.textContent = "Synced account";
    elements.profileAvatar.textContent = state.user.display_name.slice(0, 1).toUpperCase();
  } else {
    elements.profileName.textContent = "Guest mode";
    elements.profileSubtitle.textContent = "Sign in to sync";
    elements.profileAvatar.textContent = "G";
  }
}

function renderMacroCards() {
  const totals = totalsFor();
  const macros = [
    { label: "Calories", key: "calories", goal: "calorie_goal", unit: "kcal", color: "#e21833" },
    { label: "Protein", key: "protein_g", goal: "protein_goal_g", unit: "g", color: "#2b68c9" },
    { label: "Carbs", key: "carbs_g", goal: "carbs_goal_g", unit: "g", color: "#f1b82d" },
    { label: "Fat", key: "fat_g", goal: "fat_goal_g", unit: "g", color: "#7154a5" },
  ];
  elements.macroGrid.innerHTML = macros
    .map((macro) => {
      const consumed = totals[macro.key];
      const goal = state.goals[macro.goal];
      const progress = Math.min((consumed / Math.max(goal, 1)) * 100, 100);
      const remaining = Math.max(goal - consumed, 0);
      const over = Math.max(consumed - goal, 0);
      return `
        <article class="macro-card ${over > 0 ? "over-target" : ""}" style="--macro-color:${macro.color}">
          <div class="macro-ring" style="--progress:${progress.toFixed(1)}">
            <strong>${Math.round(progress)}%</strong>
          </div>
          <div class="macro-copy">
            <span>${macro.label}</span>
            <h3>${formatNumber(consumed, 1)}<small>${macro.unit}</small></h3>
            <small>${over > 0 ? `${formatNumber(over, 1)} ${macro.unit} over target` : `${formatNumber(remaining, 1)} ${macro.unit} remaining`}</small>
          </div>
        </article>`;
    })
    .join("");
}

function renderNutritionGuidance() {
  const totals = totalsFor();
  const guidance = [];
  const checks = [
    ["calories", "calorie_goal", "Calories", "If your goal is weight change, repeated calorie overages can slow or reverse the result you expect."],
    ["protein_g", "protein_goal_g", "Protein", "More protein after your target is met is not automatically more useful; leave room for carbohydrates, fats, and varied foods."],
    ["carbs_g", "carbs_goal_g", "Carbohydrates", "Favor fiber-rich choices and balance the rest of today’s plate instead of chasing a perfect number."],
    ["fat_g", "fat_goal_g", "Fat", "High-fat portions add calories quickly, so choose a lighter next item if that fits your goal."],
  ];
  checks.forEach(([key, goalKey, label, message]) => {
    const goal = Number(state.goals[goalKey] || 0);
    const consumed = Number(totals[key] || 0);
    if (goal > 0 && consumed > goal) {
      const percentage = Math.round(((consumed - goal) / goal) * 100);
      guidance.push(`<div class="guidance-card"><strong>${escapeHTML(label)} is ${percentage}% over your target.</strong>${escapeHTML(message)}</div>`);
    }
  });
  elements.nutritionGuidance.innerHTML = guidance.join("");
}

function renderLog() {
  elements.logCount.textContent = state.logs.length;
  elements.logEmpty.classList.toggle("hidden", state.logs.length > 0);
  elements.logList.innerHTML = state.logs
    .map(
      (log) => `
      <div class="log-item" data-log-id="${escapeHTML(log.id)}">
        <div>
          <strong title="${escapeHTML(log.food_name)}">${escapeHTML(log.food_name)}</strong>
          <small>${formatNumber(log.calories_per_serving * log.servings)} kcal · ${formatNumber(log.protein_per_serving_g * log.servings, 1)}g protein</small>
          <span class="portion-guide">${escapeHTML(portionGuidance(log.food_name, log.serving_size, log.servings))}</span>
        </div>
        <div class="log-item-actions">
          <div class="serving-control" aria-label="Servings">
            <button data-action="decrease-log" aria-label="Decrease serving">−</button>
            <span>${formatNumber(log.servings, 1)}×</span>
            <button data-action="increase-log" aria-label="Increase serving">+</button>
          </div>
          <button class="delete-log" data-action="delete-log" aria-label="Remove ${escapeHTML(log.food_name)}">×</button>
        </div>
      </div>`,
    )
    .join("");
  const totals = totalsFor();
  elements.logTotals.innerHTML = [
    ["Calories", totals.calories],
    ["Protein", totals.protein_g],
    ["Carbs", totals.carbs_g],
    ["Fat", totals.fat_g],
  ]
    .map(([label, value]) => `<div class="log-total"><strong>${formatNumber(value, 1)}</strong><span>${label}</span></div>`)
    .join("");
}

function favoriteIds() {
  return new Set(state.favorites.map((item) => String(item.food_id)));
}

function visibleFoods() {
  const query = state.search.trim().toLowerCase();
  return state.menu.filter((item) => !query || item.name.toLowerCase().includes(query) || item.station.toLowerCase().includes(query));
}

function renderMenu() {
  const foods = visibleFoods();
  const visible = foods.slice(0, state.visibleCount);
  const favorites = favoriteIds();
  elements.resultCount.textContent = `${foods.length} item${foods.length === 1 ? "" : "s"}`;
  elements.menuDateTitle.textContent = isTodaySelected() ? `Current ${state.meal.toLowerCase()} menu` : `${formatDate(state.date)} menu`;
  elements.loadMore.classList.toggle("hidden", visible.length >= foods.length);
  elements.foodGrid.innerHTML = visible.length
    ? visible
        .map((food) => {
          const badges = [
            ...food.dietary_labels.slice(0, 2).map((label) => `<span class="dietary-label">${escapeHTML(labelText(label))}</span>`),
            ...food.allergens.slice(0, 2).map((label) => `<span class="dietary-label allergen-label">${escapeHTML(labelText(label))}</span>`),
          ].join("");
          return `
          <article class="food-card" data-availability-id="${food.availability_id}">
            <div class="food-card-top">
              <div>
                <span class="food-station">${escapeHTML(food.station)}</span>
                <h3>${escapeHTML(food.name)}</h3>
                <span class="serving-copy">${escapeHTML(food.serving_size || "1 serving")}</span>
                <span class="portion-guide">${escapeHTML(portionGuidance(food.name, food.serving_size))}</span>
              </div>
              <button class="favorite-button ${favorites.has(String(food.id)) ? "active" : ""}" data-action="favorite" aria-label="Favorite ${escapeHTML(food.name)}">${favorites.has(String(food.id)) ? "♥" : "♡"}</button>
            </div>
            <div class="dietary-icons">${badges}</div>
            <div class="food-card-footer">
              <div class="food-macros">
                <span><strong>${formatNumber(food.calories)}</strong>kcal</span>
                <span><strong>${formatNumber(food.protein_g, 1)}g</strong>protein</span>
                <span><strong>${formatNumber(food.carbs_g, 1)}g</strong>carbs</span>
              </div>
              <button class="add-food-button" data-action="add-food" aria-label="Log ${escapeHTML(food.name)}" ${isTodaySelected() ? "" : "disabled title=\"Future menus are for planning only\""}>${isTodaySelected() ? "+" : "⌕"}</button>
            </div>
          </article>`;
        })
        .join("")
    : `<div class="empty-collection"><strong>No foods match these filters.</strong><br />Try another hall, meal, or dietary setting.</div>`;
}

function renderActiveFilters() {
  const filters = [
    ...(state.station ? [state.station] : []),
    ...state.preferences.dietary_preferences,
    ...state.preferences.excluded_labels.map((item) => `No ${labelText(item)}`),
  ];
  elements.activeFilters.innerHTML = filters.map((label) => `<span class="filter-chip">${escapeHTML(labelText(label))}</span>`).join("");
}

function renderRecommendations() {
  if (!state.recommendations.length) {
    const totals = totalsFor();
    const targetsMet = totals.calories >= state.goals.calorie_goal || remainingMacros().calories < 150;
    elements.recommendationGrid.innerHTML = `<div class="empty-collection" style="color:#aaa8a4;grid-column:1/-1">${targetsMet ? "You’re at or near today’s target, so we’re not suggesting another full meal." : "No recommendation is available for this dining hall and meal period yet."}</div>`;
    return;
  }
  elements.recommendationGrid.innerHTML = state.recommendations
    .map(
      (plan, index) => `
      <article class="recommendation-card" data-plan-index="${index}">
        <div class="recommendation-topline">
          <span class="recommendation-badge">${escapeHTML(plan.strategy.replace("-", " "))}</span>
          <span class="food-station">${plan.items.length} item${plan.items.length === 1 ? "" : "s"}</span>
        </div>
        <h3>${escapeHTML(plan.title)}</h3>
        <p>${escapeHTML(plan.explanation)}</p>
        <div class="recommendation-foods">
          ${plan.items.map((item) => `<div class="recommendation-food"><span>${escapeHTML(item.name)}<small class="portion-guide">${escapeHTML(portionGuidance(item.name, item.serving_size, item.servings))}</small></span><span>${formatNumber(item.servings, 1)}× · ${formatNumber(item.calories)} kcal</span></div>`).join("")}
        </div>
        <div class="recommendation-footer">
          <div class="recommendation-macros"><strong>${formatNumber(plan.totals.calories)} kcal</strong> · ${formatNumber(plan.totals.protein_g, 1)}g P · ${formatNumber(plan.totals.carbs_g, 1)}g C · ${formatNumber(plan.totals.fat_g, 1)}g F</div>
          <button class="add-plan-button" data-action="add-plan" ${isTodaySelected() ? "" : "disabled"}>${isTodaySelected() ? "Add meal" : "Preview only"}</button>
        </div>
      </article>`,
    )
    .join("");
}

function renderFavorites() {
  elements.favoritesList.innerHTML = state.favorites.length
    ? state.favorites
        .slice(0, 5)
        .map(
          (item) => `
          <div class="compact-item">
            <div><strong>${escapeHTML(item.name)}</strong><small>${formatNumber(item.calories)} kcal · ${formatNumber(item.protein_g, 1)}g protein</small></div>
            <span class="available-pill">${item.available_today ? "Available today" : "Saved"}</span>
          </div>`,
        )
        .join("")
    : `<div class="empty-collection">Tap the heart on a menu item to keep it close.</div>`;
}

function renderSavedMeals() {
  elements.savedMealsList.innerHTML = state.savedMeals.length
    ? state.savedMeals
        .slice(0, 4)
        .map((meal, index) => {
          const calories = meal.items.reduce((sum, item) => sum + Number(item.calories || 0), 0);
          return `<button class="compact-item" data-saved-meal-index="${index}" style="width:100%;border-left:0;border-right:0;border-top:0;background:none;text-align:left;cursor:pointer">
            <div><strong>${escapeHTML(meal.name)}</strong><small>${meal.items.length} items · ${formatNumber(calories)} kcal</small></div>
            <span class="available-pill">Log meal +</span>
          </button>`;
        })
        .join("")
    : `<div class="empty-collection">Save today’s plate to repeat it in one tap.</div>`;
}

function renderHistory() {
  const days = Array.from({ length: 7 }, (_, index) => dateWithOffset(index - 6));
  const totals = days.map((day) => {
    const logs = state.historyLogs.filter((log) => localDateString(apiDateTime(log.eaten_at)) === day);
    return { day, calories: totalsFor(logs).calories };
  });
  const max = Math.max(...totals.map((item) => item.calories), state.goals.calorie_goal, 1);
  const nonzero = totals.filter((item) => item.calories > 0);
  const average = nonzero.length ? nonzero.reduce((sum, item) => sum + item.calories, 0) / nonzero.length : 0;
  elements.weeklyAverage.textContent = `${formatNumber(average)} kcal avg`;
  elements.historyChart.innerHTML = totals
    .map((item) => {
      const height = Math.max((item.calories / max) * 100, item.calories ? 3 : 0);
      const label = new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(new Date(`${item.day}T12:00:00`)).slice(0, 1);
      return `<div class="history-day" title="${formatNumber(item.calories)} calories"><div class="history-bar-track"><div class="history-bar" style="height:${height}%"></div></div><small>${label}</small></div>`;
    })
    .join("");
}

function renderAll() {
  renderProfile();
  renderMacroCards();
  renderNutritionGuidance();
  renderLog();
  renderMenu();
  renderActiveFilters();
  renderRecommendations();
  renderFavorites();
  renderSavedMeals();
  renderHistory();
}

async function restoreSession() {
  if (!state.token) return;
  try {
    state.user = await api("/auth/me");
  } catch {
    clearSession();
  }
}

function renderMenuControls() {
  const dates = state.menuContext?.dates || [{ date: state.date, meal_periods: [state.meal], item_count: 0 }];
  elements.date.innerHTML = dates
    .map((item) => {
      const label = item.date === state.menuContext?.today ? "Today" : formatDate(item.date);
      return `<option value="${item.date}">${escapeHTML(label)}${item.item_count ? ` · ${formatNumber(item.item_count)} items` : ""}</option>`;
    })
    .join("");
  elements.date.value = state.date;
  const meals = allowedMeals();
  document.querySelectorAll(".meal-tab").forEach((button) => {
    const available = meals.includes(button.dataset.meal);
    button.disabled = !available;
    button.hidden = !available;
    button.classList.toggle("active", button.dataset.meal === state.meal);
  });
  document.querySelector("#custom-food-button").disabled = !isTodaySelected();
  document.querySelector("#save-meal-button").disabled = !isTodaySelected();
  elements.todayLabel.textContent = formatDate(state.date).toUpperCase();
}

async function loadMenuContext({ preserveDate = true } = {}) {
  const context = await api("/menu-context");
  state.menuContext = context;
  const publishedDates = new Set(context.dates.map((item) => item.date));
  if (!preserveDate || !publishedDates.has(state.date)) state.date = context.today;
  syncSelectedMeal();
  renderMenuControls();
  return context;
}

function watchLiveRefresh() {
  if (state.refreshPoll) clearTimeout(state.refreshPoll);
  if (state.menuContext?.refresh_status !== "refreshing") return;
  state.refreshPoll = setTimeout(async () => {
    try {
      const wasRefreshing = state.menuContext?.refresh_status === "refreshing";
      await loadMenuContext();
      if (wasRefreshing && state.menuContext.refresh_status !== "refreshing") {
        await loadHalls();
        await loadStations();
        await Promise.all([loadMenu(), loadRecommendations()]);
        toast("Live UMD menus are up to date");
      }
      renderFreshness();
      watchLiveRefresh();
    } catch {
      state.refreshPoll = setTimeout(watchLiveRefresh, 10000);
    }
  }, 5000);
}

async function loadHalls() {
  state.halls = await api(`/halls?date=${state.date}`);
  elements.hall.innerHTML = `<option value="">All dining halls</option>${state.halls
    .map((hall) => `<option value="${escapeHTML(hall.slug)}">${escapeHTML(hall.name)}${hall.item_count ? ` · ${hall.item_count}` : ""}</option>`)
    .join("")}`;
  if (!state.hall) state.hall = state.halls.find((hall) => hall.slug === "yahentamitsi")?.slug || state.halls[0]?.slug || "";
  if (!state.halls.some((hall) => hall.slug === state.hall)) state.hall = "";
  elements.hall.value = state.hall;
}

async function loadStations() {
  const params = new URLSearchParams({ date: state.date, meal: state.meal });
  if (state.hall) params.set("hall", state.hall);
  state.stations = await api(`/stations?${params}`);
  if (!state.stations.some((station) => station.name === state.station)) {
    state.station = "";
  }
  elements.station.innerHTML = `<option value="">All stations</option>${state.stations
    .map((station) => `<option value="${escapeHTML(station.name)}">${escapeHTML(station.name)} · ${formatNumber(station.item_count)}</option>`)
    .join("")}`;
  elements.station.value = state.station;
  renderActiveFilters();
}

async function loadPersonalData() {
  if (state.user) {
    const start = dateWithOffset(-6);
    const [goals, preferences, logs, favorites, savedMeals] = await Promise.all([
      api(`/users/me/goals?date=${state.date}`),
      api("/users/me/preferences"),
      api(`/users/me/logs?date_from=${start}&date_to=${state.date}`),
      api(`/users/me/favorites?date=${state.date}`),
      api("/users/me/saved-meals"),
    ]);
    state.goals = goals;
    state.preferences = preferences;
    state.historyLogs = logs;
    state.logs = logs.filter((log) => localDateString(apiDateTime(log.eaten_at)) === state.date);
    state.favorites = favorites;
    state.savedMeals = savedMeals;
  } else {
    state.goals = { ...DEFAULT_GOALS, ...readStorage(STORAGE.goals, {}) };
    state.preferences = { ...DEFAULT_PREFERENCES, ...readStorage(STORAGE.preferences, {}) };
    state.historyLogs = readStorage(STORAGE.logs, []);
    state.logs = state.historyLogs.filter((log) => localDateString(apiDateTime(log.eaten_at)) === state.date);
    state.favorites = readStorage(STORAGE.favorites, []);
    state.savedMeals = readStorage(STORAGE.meals, []);
  }
}

async function loadMenu() {
  elements.foodGrid.innerHTML = Array.from({ length: 6 }, () => `<div class="skeleton"></div>`).join("");
  const params = new URLSearchParams({ date: state.date, meal: state.meal, limit: "500" });
  if (state.hall) params.set("hall", state.hall);
  if (state.station) params.set("station", state.station);
  state.preferences.dietary_preferences.forEach((label) => params.append("dietary", label));
  state.preferences.excluded_labels.forEach((label) => params.append("exclude", label));
  try {
    const response = await api(`/foods?${params}`);
    state.menu = response.items;
    state.menuTotal = response.total;
    state.lastScrapedAt = response.last_scraped_at;
    state.visibleCount = 12;
    renderMenu();
    renderFreshness();
  } catch (error) {
    state.menu = [];
    renderMenu();
    elements.freshness.innerHTML = `<span class="live-dot" style="background:#e21833"></span><span>Menu API unavailable</span>`;
    toast(error.message);
  }
}

function renderFreshness() {
  if (state.menuContext?.refresh_status === "refreshing") {
    elements.freshness.innerHTML = `<span class="live-dot pulse"></span><span>Checking UMD for live updates…</span>`;
    return;
  }
  if (!state.lastScrapedAt) {
    elements.freshness.innerHTML = `<span class="live-dot" style="background:#f1b82d"></span><span>No scrape recorded for this date</span>`;
    return;
  }
  const formatted = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit", month: "short", day: "numeric" }).format(apiDateTime(state.lastScrapedAt));
  elements.freshness.innerHTML = `<span class="live-dot"></span><span>Live UMD menu · checked ${escapeHTML(formatted)}</span>`;
}

async function loadRecommendations() {
  elements.recommendationGrid.innerHTML = Array.from({ length: 3 }, () => `<div class="skeleton" style="background:#292929;min-height:300px"></div>`).join("");
  try {
    const response = await api("/recommendations", {
      method: "POST",
      body: JSON.stringify({
        hall: state.hall || null,
        menu_date: state.date,
        meal: state.meal,
        remaining: remainingMacros(),
        excluded_labels: state.preferences.excluded_labels,
        dietary_preferences: state.preferences.dietary_preferences,
      }),
    });
    state.recommendations = response.plans;
  } catch {
    state.recommendations = [];
  }
  renderRecommendations();
}

function findFood(availabilityId) {
  return state.menu.find((item) => String(item.availability_id) === String(availabilityId));
}

function guestLogFromFood(food, servings = 1) {
  return {
    id: crypto.randomUUID(),
    food_id: food.id,
    availability_id: food.availability_id,
    food_name: food.name,
    serving_size: food.serving_size,
    servings,
    meal_type: state.meal,
    eaten_at: selectedDateTime(),
    calories_per_serving: Number(food.calories || 0),
    protein_per_serving_g: Number(food.protein_g || 0),
    carbs_per_serving_g: Number(food.carbs_g || 0),
    fat_per_serving_g: Number(food.fat_g || 0),
  };
}

async function logFood(food, servings = 1, quiet = false) {
  if (!isTodaySelected()) throw new Error("Future menus are for planning; foods can only be logged today");
  let log;
  if (state.user) {
    log = await api("/users/me/logs", {
      method: "POST",
      body: JSON.stringify({ availability_id: food.availability_id, servings, meal_type: state.meal, eaten_at: selectedDateTime() }),
    });
  } else {
    log = guestLogFromFood(food, servings);
    const allLogs = readStorage(STORAGE.logs, []);
    allLogs.push(log);
    writeStorage(STORAGE.logs, allLogs);
  }
  state.logs.unshift(log);
  state.historyLogs.unshift(log);
  renderMacroCards();
  renderNutritionGuidance();
  renderLog();
  renderHistory();
  if (!quiet) toast(`${food.name} added to today`);
}

async function addCustomFood(payload) {
  let log;
  if (state.user) {
    log = await api("/users/me/logs", { method: "POST", body: JSON.stringify(payload) });
  } else {
    log = {
      id: crypto.randomUUID(),
      food_id: null,
      availability_id: null,
      food_name: payload.custom_name,
      serving_size: "1 serving",
      servings: 1,
      meal_type: state.meal,
      eaten_at: payload.eaten_at,
      calories_per_serving: payload.calories,
      protein_per_serving_g: payload.protein_g,
      carbs_per_serving_g: payload.carbs_g,
      fat_per_serving_g: payload.fat_g,
    };
    const allLogs = readStorage(STORAGE.logs, []);
    allLogs.push(log);
    writeStorage(STORAGE.logs, allLogs);
  }
  state.logs.unshift(log);
  state.historyLogs.unshift(log);
  renderMacroCards();
  renderNutritionGuidance();
  renderLog();
  renderHistory();
}

async function updateLog(log, servings) {
  if (servings <= 0) return deleteLog(log);
  if (state.user) {
    const updated = await api(`/users/me/logs/${log.id}`, { method: "PATCH", body: JSON.stringify({ servings }) });
    Object.assign(log, updated);
  } else {
    log.servings = servings;
    writeStorage(STORAGE.logs, state.historyLogs);
  }
  renderMacroCards();
  renderNutritionGuidance();
  renderLog();
  renderHistory();
}

async function deleteLog(log) {
  if (state.user) await api(`/users/me/logs/${log.id}`, { method: "DELETE" });
  state.logs = state.logs.filter((item) => item.id !== log.id);
  state.historyLogs = state.historyLogs.filter((item) => item.id !== log.id);
  if (!state.user) writeStorage(STORAGE.logs, state.historyLogs);
  renderMacroCards();
  renderNutritionGuidance();
  renderLog();
  renderHistory();
  toast("Food removed from today");
}

async function toggleFavorite(food) {
  const isFavorite = favoriteIds().has(String(food.id));
  if (state.user) {
    await api(isFavorite ? `/users/me/favorites/${food.id}` : "/users/me/favorites", {
      method: isFavorite ? "DELETE" : "POST",
      body: isFavorite ? undefined : JSON.stringify({ food_id: food.id }),
    });
    state.favorites = await api(`/users/me/favorites?date=${state.date}`);
  } else if (isFavorite) {
    state.favorites = state.favorites.filter((item) => String(item.food_id) !== String(food.id));
  } else {
    state.favorites.push({
      food_id: food.id,
      name: food.name,
      serving_size: food.serving_size,
      calories: food.calories,
      protein_g: food.protein_g,
      carbs_g: food.carbs_g,
      fat_g: food.fat_g,
      available_today: true,
      halls_today: [food.hall_name],
    });
  }
  if (!state.user) writeStorage(STORAGE.favorites, state.favorites);
  renderMenu();
  renderFavorites();
}

async function addRecommendationPlan(plan) {
  for (const item of plan.items) {
    const food = findFood(item.availability_id) || {
      id: item.food_id,
      availability_id: item.availability_id,
      name: item.name,
      serving_size: item.serving_size,
      calories: item.calories / item.servings,
      protein_g: item.protein_g / item.servings,
      carbs_g: item.carbs_g / item.servings,
      fat_g: item.fat_g / item.servings,
    };
    await logFood(food, item.servings, true);
  }
  toast(`${plan.title} added to today`);
  await loadRecommendations();
}

async function saveCurrentMeal() {
  const usable = state.logs.filter((log) => log.food_id);
  if (!usable.length) return toast("Add at least one dining hall food first");
  document.querySelector("#save-meal-name").value = `${state.meal} favorites`;
  document.querySelector("#save-meal-modal").showModal();
}

async function submitSavedMeal(name) {
  const usable = state.logs.filter((log) => log.food_id);
  if (!usable.length) throw new Error("Add at least one dining hall food first");
  if (!name?.trim()) return;
  const grouped = new Map();
  usable.forEach((log) => grouped.set(log.food_id, (grouped.get(log.food_id) || 0) + Number(log.servings)));
  if (state.user) {
    const meal = await api("/users/me/saved-meals", {
      method: "POST",
      body: JSON.stringify({ name: name.trim(), items: [...grouped].map(([food_id, servings]) => ({ food_id, servings })) }),
    });
    state.savedMeals.unshift(meal);
  } else {
    const items = [...grouped].map(([foodId, servings]) => {
      const log = usable.find((item) => item.food_id === foodId);
      return {
        food_id: foodId,
        name: log.food_name,
        serving_size: log.serving_size,
        servings,
        calories: log.calories_per_serving * servings,
        protein_g: log.protein_per_serving_g * servings,
        carbs_g: log.carbs_per_serving_g * servings,
        fat_g: log.fat_per_serving_g * servings,
      };
    });
    state.savedMeals.unshift({ id: crypto.randomUUID(), name: name.trim(), created_at: new Date().toISOString(), items });
    writeStorage(STORAGE.meals, state.savedMeals);
  }
  renderSavedMeals();
  toast("Meal saved for later");
}

async function logSavedMeal(meal) {
  for (const item of meal.items) {
    const available = state.menu.find((food) => String(food.id) === String(item.food_id));
    if (available) {
      await logFood(available, item.servings, true);
    } else {
      await addCustomFood({
        custom_name: item.name,
        serving_size: item.serving_size,
        servings: 1,
        meal_type: state.meal,
        eaten_at: selectedDateTime(),
        calories: item.calories,
        protein_g: item.protein_g,
        carbs_g: item.carbs_g,
        fat_g: item.fat_g,
      });
    }
  }
  toast(`${meal.name} added to today`);
  await loadRecommendations();
}

function openGoalsModal() {
  document.querySelector("#goal-calories").value = state.goals.calorie_goal;
  document.querySelector("#goal-protein").value = state.goals.protein_goal_g;
  document.querySelector("#goal-carbs").value = state.goals.carbs_goal_g;
  document.querySelector("#goal-fat").value = state.goals.fat_goal_g;
  document.querySelector("#goals-modal").showModal();
}

function openSettingsModal() {
  document.querySelectorAll('[name="dietary"]').forEach((input) => {
    input.checked = state.preferences.dietary_preferences.includes(input.value);
  });
  document.querySelectorAll('[name="exclude"]').forEach((input) => {
    input.checked = state.preferences.excluded_labels.includes(input.value);
  });
  const profile = { ...DEFAULT_PREFERENCES.profile, ...(state.preferences.profile || {}) };
  const totalInches = profile.height_cm ? profile.height_cm / 2.54 : 0;
  document.querySelector("#profile-age").value = profile.age || "";
  document.querySelector("#profile-gender").value = profile.gender || "";
  document.querySelector("#profile-height-ft").value = totalInches ? Math.floor(totalInches / 12) : "";
  document.querySelector("#profile-height-in").value = totalInches ? Math.round(totalInches % 12) : "";
  document.querySelector("#profile-weight").value = profile.weight_kg ? (profile.weight_kg * 2.20462).toFixed(1) : "";
  document.querySelector("#profile-activity").value = profile.activity_level;
  document.querySelector("#profile-goal").value = profile.goal_type;
  document.querySelector("#profile-use-targets").checked = profile.use_profile_targets;
  renderTargetPreview();
  document.querySelector("#settings-modal").showModal();
}

function configureAuthModal() {
  const register = state.authMode === "register";
  document.querySelector("#auth-title").textContent = register ? "Create your account" : "Sync your progress";
  document.querySelector("#auth-submit").textContent = register ? "Create account" : "Sign in";
  document.querySelector("#switch-auth").textContent = register ? "Already have an account? Sign in" : "New here? Create an account";
  document.querySelector("#name-field").classList.toggle("hidden", !register);
  document.querySelector("#auth-name").required = register;
  document.querySelector("#auth-password").autocomplete = register ? "new-password" : "current-password";
  document.querySelector("#password-hint").textContent = register ? "Use at least 10 characters." : "Use your account password.";
  document.querySelector("#auth-error").textContent = "";
}

async function migrateGuestData() {
  const guestLogs = readStorage(STORAGE.logs, []);
  const guestFavorites = readStorage(STORAGE.favorites, []);
  const guestGoals = { ...DEFAULT_GOALS, ...readStorage(STORAGE.goals, {}) };
  const guestPreferences = { ...DEFAULT_PREFERENCES, ...readStorage(STORAGE.preferences, {}) };
  const requests = [];
  guestLogs.forEach((log) => {
    requests.push(
      api("/users/me/logs", {
        method: "POST",
        body: JSON.stringify(
          log.availability_id
            ? { availability_id: log.availability_id, servings: log.servings, meal_type: log.meal_type, eaten_at: log.eaten_at }
            : { custom_name: log.food_name, serving_size: log.serving_size, servings: log.servings, meal_type: log.meal_type, eaten_at: log.eaten_at, calories: log.calories_per_serving, protein_g: log.protein_per_serving_g, carbs_g: log.carbs_per_serving_g, fat_g: log.fat_per_serving_g },
        ),
      }).catch(() => null),
    );
  });
  guestFavorites.forEach((favorite) => requests.push(api("/users/me/favorites", { method: "POST", body: JSON.stringify({ food_id: favorite.food_id }) }).catch(() => null)));
  requests.push(api("/users/me/goals", { method: "PUT", body: JSON.stringify({ ...guestGoals, goal_date: state.date, save_as_default: true }) }).catch(() => null));
  requests.push(api("/users/me/preferences", { method: "PUT", body: JSON.stringify(guestPreferences) }).catch(() => null));
  await Promise.all(requests);
  [STORAGE.logs, STORAGE.favorites, STORAGE.goals, STORAGE.preferences].forEach((key) => localStorage.removeItem(key));
}

async function initialize() {
  elements.todayLabel.textContent = formatDate(state.date).toUpperCase();
  document.querySelectorAll(".meal-tab").forEach((button) => button.classList.toggle("active", button.dataset.meal === state.meal));
  document.querySelector("#exclusion-choices").innerHTML = EXCLUSION_LABELS.map(
    (label) => `<label class="choice-chip"><input type="checkbox" name="exclude" value="${label}" /> ${escapeHTML(labelText(label))}</label>`,
  ).join("");
  renderAll();
  await restoreSession();
  try {
    await loadMenuContext({ preserveDate: false });
    await loadPersonalData();
    await loadHalls();
    await loadStations();
    renderAll();
    await Promise.all([loadMenu(), loadRecommendations()]);
    watchLiveRefresh();
  } catch (error) {
    toast(error.message);
  }
  if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("/sw.js").catch(() => {});
}

document.querySelector("#meal-tabs").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-meal]");
  if (!button || button.disabled) return;
  state.meal = button.dataset.meal;
  state.station = "";
  document.querySelectorAll(".meal-tab").forEach((item) => item.classList.toggle("active", item === button));
  await loadStations();
  await Promise.all([loadMenu(), loadRecommendations()]);
});

elements.date.addEventListener("change", async () => {
  state.date = elements.date.value;
  state.station = "";
  syncSelectedMeal();
  renderMenuControls();
  await loadPersonalData();
  await loadHalls();
  await loadStations();
  renderAll();
  await Promise.all([loadMenu(), loadRecommendations()]);
});

elements.hall.addEventListener("change", async () => {
  state.hall = elements.hall.value;
  state.station = "";
  localStorage.setItem(STORAGE.hall, state.hall);
  await loadStations();
  await Promise.all([loadMenu(), loadRecommendations()]);
});

elements.station.addEventListener("change", async () => {
  state.station = elements.station.value;
  state.visibleCount = 12;
  renderActiveFilters();
  await loadMenu();
});

elements.search.addEventListener("input", () => {
  state.search = elements.search.value;
  state.visibleCount = 12;
  renderMenu();
});

elements.loadMore.addEventListener("click", () => {
  state.visibleCount += 12;
  renderMenu();
});

elements.foodGrid.addEventListener("click", async (event) => {
  const card = event.target.closest("[data-availability-id]");
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (!card || !action) return;
  const food = findFood(card.dataset.availabilityId);
  if (!food) return;
  try {
    if (action === "add-food") {
      await logFood(food);
      await loadRecommendations();
    } else if (action === "favorite") {
      await toggleFavorite(food);
    }
  } catch (error) {
    toast(error.message);
    if (error.message.toLowerCase().includes("no longer available")) await loadMenu();
  }
});

elements.logList.addEventListener("click", async (event) => {
  const row = event.target.closest("[data-log-id]");
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (!row || !action) return;
  const log = state.logs.find((item) => item.id === row.dataset.logId);
  if (!log) return;
  try {
    if (action === "delete-log") await deleteLog(log);
    if (action === "increase-log") await updateLog(log, Number(log.servings) + 0.5);
    if (action === "decrease-log") await updateLog(log, Number(log.servings) - 0.5);
    await loadRecommendations();
  } catch (error) {
    toast(error.message);
  }
});

elements.recommendationGrid.addEventListener("click", async (event) => {
  const card = event.target.closest("[data-plan-index]");
  if (!card || !event.target.closest('[data-action="add-plan"]')) return;
  try {
    await addRecommendationPlan(state.recommendations[Number(card.dataset.planIndex)]);
  } catch (error) {
    toast(error.message);
  }
});

elements.savedMealsList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-saved-meal-index]");
  if (!button) return;
  try {
    await logSavedMeal(state.savedMeals[Number(button.dataset.savedMealIndex)]);
  } catch (error) {
    toast(error.message);
  }
});

document.querySelector("#edit-goals-button").addEventListener("click", openGoalsModal);
document.querySelector("#settings-button").addEventListener("click", openSettingsModal);
document.querySelector("#custom-food-button").addEventListener("click", () => document.querySelector("#custom-food-modal").showModal());
document.querySelector("#save-meal-button").addEventListener("click", () => saveCurrentMeal().catch((error) => toast(error.message)));

document.querySelector("#save-meal-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await submitSavedMeal(document.querySelector("#save-meal-name").value);
    document.querySelector("#save-meal-modal").close();
  } catch (error) {
    toast(error.message);
  }
});

document.querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog")?.close());
});

document.querySelector(".profile-group").addEventListener("input", renderTargetPreview);
document.querySelector(".profile-group").addEventListener("change", renderTargetPreview);

document.querySelector("#profile-button").addEventListener("click", async () => {
  if (!state.user) {
    state.authMode = "login";
    configureAuthModal();
    document.querySelector("#auth-modal").showModal();
    return;
  }
  if (!window.confirm(`Sign out of ${state.user.email}?`)) return;
  try { await api("/auth/logout", { method: "POST" }); } catch {}
  clearSession();
  await loadPersonalData();
  renderAll();
  toast("Signed out — guest mode is active");
});

document.querySelector("#switch-auth").addEventListener("click", () => {
  state.authMode = state.authMode === "login" ? "register" : "login";
  configureAuthModal();
});

document.querySelector("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#auth-error");
  error.textContent = "";
  const register = state.authMode === "register";
  const body = {
    email: document.querySelector("#auth-email").value,
    password: document.querySelector("#auth-password").value,
  };
  if (register) body.display_name = document.querySelector("#auth-name").value;
  try {
    const response = await api(register ? "/auth/register" : "/auth/login", { method: "POST", body: JSON.stringify(body) });
    state.token = response.access_token;
    state.user = response.user;
    localStorage.setItem(STORAGE.token, state.token);
    if (register) await migrateGuestData();
    await loadPersonalData();
    renderAll();
    document.querySelector("#auth-modal").close();
    toast(register ? "Account created and guest data synced" : "Welcome back");
  } catch (requestError) {
    error.textContent = requestError.message;
  }
});

document.querySelector("#goals-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = {
    calorie_goal: Number(document.querySelector("#goal-calories").value),
    protein_goal_g: Number(document.querySelector("#goal-protein").value),
    carbs_goal_g: Number(document.querySelector("#goal-carbs").value),
    fat_goal_g: Number(document.querySelector("#goal-fat").value),
  };
  try {
    if (state.user) {
      state.goals = await api("/users/me/goals", { method: "PUT", body: JSON.stringify({ ...values, goal_date: state.date, save_as_default: document.querySelector("#save-default-goals").checked }) });
    } else {
      state.goals = values;
      writeStorage(STORAGE.goals, values);
    }
    document.querySelector("#goals-modal").close();
    renderMacroCards();
    renderNutritionGuidance();
    renderHistory();
    await loadRecommendations();
    toast("Macro goals updated");
  } catch (error) {
    toast(error.message);
  }
});

document.querySelector("#settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const profile = profileFromForm();
  const estimatedGoals = suggestedGoals(profile);
  const preferences = {
    dietary_preferences: [...document.querySelectorAll('[name="dietary"]:checked')].map((input) => input.value),
    excluded_labels: [...document.querySelectorAll('[name="exclude"]:checked')].map((input) => input.value),
    favorite_hall_id: state.preferences.favorite_hall_id || null,
    profile,
  };
  try {
    if (state.user) state.preferences = await api("/users/me/preferences", { method: "PUT", body: JSON.stringify(preferences) });
    else {
      state.preferences = preferences;
      writeStorage(STORAGE.preferences, preferences);
    }
    if (profile.use_profile_targets && estimatedGoals) {
      if (state.user) {
        state.goals = await api("/users/me/goals", {
          method: "PUT",
          body: JSON.stringify({ ...estimatedGoals, goal_date: state.date, save_as_default: true }),
        });
      } else {
        state.goals = estimatedGoals;
        writeStorage(STORAGE.goals, estimatedGoals);
      }
    }
    document.querySelector("#settings-modal").close();
    renderAll();
    await Promise.all([loadMenu(), loadRecommendations()]);
    toast(profile.use_profile_targets && estimatedGoals ? "Profile saved and personalized targets applied" : "Profile and dietary filters saved");
  } catch (error) {
    toast(error.message);
  }
});

document.querySelector("#custom-food-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await addCustomFood({
      custom_name: document.querySelector("#custom-name").value,
      servings: 1,
      meal_type: state.meal,
      eaten_at: selectedDateTime(),
      calories: Number(document.querySelector("#custom-calories").value),
      protein_g: Number(document.querySelector("#custom-protein").value),
      carbs_g: Number(document.querySelector("#custom-carbs").value),
      fat_g: Number(document.querySelector("#custom-fat").value),
    });
    event.target.reset();
    document.querySelector("#custom-food-modal").close();
    await loadRecommendations();
    toast("Custom food added");
  } catch (error) {
    toast(error.message);
  }
});

const navigationSections = ["dashboard", "menu", "insights"].map((id) => document.getElementById(id));
function updateActiveNavigation() {
  const marker = window.scrollY + Math.max(
    document.querySelector(".topbar").offsetHeight + 80,
    window.innerHeight * 0.5,
  );
  let active = navigationSections[0];
  const nearBottom = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 24;
  if (nearBottom) active = navigationSections.at(-1);
  else {
    navigationSections.forEach((section) => {
      if (section.offsetTop <= marker) active = section;
    });
  }
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === `#${active.id}`);
  });
}
window.addEventListener("scroll", updateActiveNavigation, { passive: true });
window.addEventListener("resize", updateActiveNavigation);
updateActiveNavigation();

initialize();
