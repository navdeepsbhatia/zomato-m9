const apiUrl = String(import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

const state = {
  budget: "medium",
  minRating: 3.5,
  llmOk: null,
  locations: [],
};

const app = document.querySelector("#app");
app.append(
  shell(),
);

const form = document.querySelector("#preferences");
const locationSelect = document.querySelector("#location");
const cuisineInput = document.querySelector("#cuisine");
const notesInput = document.querySelector("#notes");
const ratingOutput = document.querySelector("#rating-output");
const ratingInput = document.querySelector("#min-rating");
const results = document.querySelector("#results");
const protocol = document.querySelector("#protocol");
const submitButton = document.querySelector("#submit");

document.querySelectorAll("[data-budget]").forEach((button) => {
  button.addEventListener("click", () => {
    state.budget = button.dataset.budget;
    document.querySelectorAll("[data-budget]").forEach((item) => {
      item.setAttribute("aria-checked", String(item === button));
    });
  });
});

ratingInput.addEventListener("input", () => {
  state.minRating = Number(ratingInput.value);
  ratingOutput.textContent = state.minRating.toFixed(1);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await search();
});

loadLocations();

function shell() {
  const page = el("main", "page");
  page.innerHTML = `
    <header class="table-top">
      <div class="table-brand">
        <span class="table-mark" aria-hidden="true">✦</span>
        <span class="table-word">Table</span>
      </div>
      <nav class="table-nav" aria-label="Table">
        <span class="nav-current">Concierge</span>
        <span class="nav-muted">Journal</span>
        <span class="nav-avatar" aria-hidden="true">☺</span>
      </nav>
    </header>
    <section class="hero">
      <div class="eyebrow">Curated gastronomy</div>
      <h1>Restaurant recommendations</h1>
      <p>Choose a neighborhood, budget, and minimum rating. Cuisine is optional.</p>
    </section>
    <form id="preferences" class="card">
      <div class="field">
        <div class="field-head"><span>Neighborhood</span><span class="field-note required">Required</span></div>
        <select id="location" class="control" name="location" required></select>
      </div>
      <div class="field">
        <div class="field-head"><span>Budget tier</span></div>
        <div class="budget" role="radiogroup" aria-label="Budget">
          <button type="button" data-budget="low" role="radio" aria-checked="false">Low  ₹</button>
          <button type="button" data-budget="medium" role="radio" aria-checked="true">Medium  ₹₹</button>
          <button type="button" data-budget="high" role="radio" aria-checked="false">High  ₹₹₹</button>
        </div>
      </div>
      <div class="field">
        <div class="field-head"><span>Cuisine preference</span><span class="field-note">Optional</span></div>
        <input id="cuisine" class="control" name="cuisine" placeholder="Italian" />
        <p class="hint">Leave blank to include every cuisine.</p>
      </div>
      <div class="field">
        <div class="rating-row">
          <label for="min-rating">Minimum rating</label>
          <span id="rating-output" class="rating-value">3.5</span>
        </div>
        <input id="min-rating" type="range" min="0" max="5" step="0.1" value="3.5" />
      </div>
      <div class="field">
        <div class="field-head"><span>Specific desires or atmosphere</span><span class="field-note">Optional</span></div>
        <textarea id="notes" class="notes" name="notes" placeholder="family-friendly, quick service"></textarea>
      </div>
      <div class="form-actions">
        <button id="submit" class="submit" type="submit" disabled>Find restaurants →</button>
        <div class="ready-line"><span class="ready-dot"></span>Concierge ready · Live Bangalore directory</div>
      </div>
    </form>
    <div id="results"></div>
    <aside id="protocol" class="protocol">
      <div class="protocol-copy">
        <span class="protocol-icon" aria-hidden="true">✦</span>
        <div>
          <strong>Private Gastronomic Protocol</strong>
          <p>Recommendations are weighted by ambiance density, acoustic balance, and provenance.</p>
        </div>
      </div>
      <span class="protocol-lock">Unsponsored</span>
    </aside>
    <footer class="table-footer">
      <span>Table AI · Gastronomy &amp; Dining Concierge</span>
      <span>© Curated Discretion</span>
    </footer>
  `;
  return page;
}

async function loadLocations() {
  if (!apiUrl) {
    showError("VITE_API_URL is not set.");
    return;
  }
  try {
    const [health, locations] = await Promise.all([
      api("/api/health"),
      api("/api/locations"),
    ]);
    state.llmOk = Boolean(health.body.checks && health.body.checks.llm && health.body.checks.llm.ok);
    if (health.status === 503) {
      const cacheDetail = health.body.checks && health.body.checks.cache && health.body.checks.cache.detail;
      showError(cacheDetail || "The restaurant cache could not be read.");
      return;
    }
    if (!locations.ok) {
      showError(locations.body.detail || "The restaurant cache could not be read.");
      return;
    }
    const names = locations.body.locations || [];
    if (!names.length) {
      showError("The restaurant cache has no locations to choose from.");
      return;
    }
    state.locations = names;
    names.forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      if (name === "Banashankari") option.selected = true;
      locationSelect.append(option);
    });
    submitButton.disabled = false;
  } catch (error) {
    showError(error.message || "The recommendation service could not be reached.");
  }
}

async function search() {
  clear(results);
  protocol.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "Finding restaurants…";
  results.className = "results";
  results.append(el("div", "skeleton"), el("div", "skeleton"), el("div", "skeleton"));
  const payload = {
    location: locationSelect.value,
    budget: state.budget,
    cuisine: cuisineInput.value,
    min_rating: state.minRating,
    additional_preferences: notesInput.value,
  };
  try {
    const response = await api("/api/recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    clear(results);
    if (!response.ok) {
      const detail = formatDetail(response.body.detail) || "The restaurant cache could not be read.";
      results.append(notice("error", response.status === 422 ? "Check the form." : "The restaurant cache could not be read.", detail));
      return;
    }
    renderResult(response.body, payload);
  } catch (error) {
    clear(results);
    results.append(notice("error", "The recommendation service could not be reached.", error.message));
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Find restaurants →";
  }
}

function renderResult(result, preferences) {
  if (result.summary && result.items && result.items.length) {
    const summary = el("p", "summary");
    summary.textContent = result.summary;
    results.append(summary);
  }
  if (result.relaxed_filters && result.relaxed_filters.length) {
    results.append(
      notice(
        "warn",
        `Relaxed filters: ${result.relaxed_filters.join(", ")}.`,
        "The shortlist was widened so a recommendation could still be made.",
      ),
    );
  }
  if (result.source === "fallback" && result.items && result.items.length) {
    const detail = state.llmOk
      ? "These cards are a fallback ranking by rating and number of votes. The model response could not be used."
      : "These cards are a fallback ranking by rating and number of votes. Live explanations need an API key.";
    results.append(notice("info", "Offline ranking", detail));
  }
  if (!result.items || !result.items.length) {
    results.append(notice("empty", "No exact dining matches", emptyCopy(preferences)));
    return;
  }
  result.items.forEach((item) => results.append(card(item)));
}

function card(item) {
  const article = el("article", "rec-card");
  const top = el("div", "rec-top");
  const name = el("div", "rec-name");
  const rank = el("span", "rec-rank");
  rank.textContent = String(item.rank);
  const heading = document.createElement("h2");
  heading.textContent = item.name || "Unavailable";
  name.append(rank, heading);
  const meta = el("div", "rec-meta");
  const rating = el("span", "rec-rating");
  rating.textContent = `★ ${item.rating == null ? "unavailable" : Number(item.rating).toFixed(1)}`;
  const dot = document.createElement("span");
  dot.textContent = "•";
  const cost = document.createElement("span");
  cost.textContent = item.cost_for_two == null ? "Cost unavailable" : `₹${Number(item.cost_for_two).toLocaleString("en-IN")} for two`;
  meta.append(rating, dot, cost);
  top.append(name, meta);
  const pills = el("div", "pills");
  cuisinePills(item.cuisines).forEach((label) => {
    const pill = el("span", "pill");
    pill.textContent = label;
    pills.append(pill);
  });
  article.append(top, pills);
  if (item.explanation) {
    const why = el("p", "rec-why");
    why.textContent = item.explanation;
    article.append(why);
  }
  const link = safeLink(item.url);
  if (link) article.append(link);
  return article;
}

function cuisinePills(value) {
  const parts = String(value || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  return parts.length ? parts : ["Unavailable"];
}

function safeLink(url) {
  const cleaned = String(url || "").trim();
  let parsed;
  try {
    parsed = new URL(cleaned);
  } catch {
    return null;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
  const link = document.createElement("a");
  link.className = "rec-link";
  link.href = cleaned;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Open restaurant →";
  return link;
}

function emptyCopy(preferences) {
  const cuisine = preferences.cuisine.trim() ? `cuisine ${preferences.cuisine.trim()}` : "any cuisine";
  return `No restaurants to show for location ${preferences.location}, ${cuisine}, budget ${preferences.budget}, and minimum rating ${preferences.min_rating}.`;
}

function notice(kind, title, detail) {
  const box = el("div", `notice notice-${kind}`);
  const icon = el("span", "notice-icon");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "✦";
  const copy = document.createElement("div");
  if (kind === "empty") {
    const heading = document.createElement("h2");
    heading.textContent = title;
    copy.append(heading);
  } else {
    const strong = document.createElement("strong");
    strong.textContent = title;
    copy.append(strong);
  }
  const paragraph = document.createElement("p");
  paragraph.textContent = detail;
  copy.append(paragraph);
  box.append(icon, copy);
  return box;
}

function showError(message) {
  form.hidden = true;
  protocol.hidden = true;
  clear(results);
  results.className = "results";
  results.append(notice("error", "The restaurant cache could not be read.", message));
}

async function api(path, options) {
  let response;
  try {
    response = await fetch(`${apiUrl}${path}`, options);
  } catch {
    throw new Error("The recommendation service could not be reached.");
  }
  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  return { ok: response.ok, status: response.status, body };
}

function formatDetail(detail) {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return "";
  return detail
    .map((item) => {
      const field = Array.isArray(item.loc) ? item.loc.join(".") : "form";
      return `${field}: ${item.msg}`;
    })
    .join("\n");
}

function el(tag, className) {
  const node = document.createElement(tag);
  node.className = className;
  return node;
}

function clear(node) {
  node.replaceChildren();
}
