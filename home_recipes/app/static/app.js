// Relative URLs throughout, so the page works behind Home Assistant's ingress path.
const view = document.getElementById("view");

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const date = (ts) => new Date(ts * 1000).toLocaleDateString("da-DK", { day: "numeric", month: "short", year: "numeric" });
const ago = (ts) => {
  if (!ts) return "aldrig lavet";
  const days = Math.floor((Date.now() / 1000 - ts) / 86400);
  return days < 1 ? "lavet i dag" : days === 1 ? "lavet i går" : `lavet for ${days} dage siden`;
};

async function api(path, options = {}) {
  const r = await fetch(`api/${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.status === 204 ? null : r.json();
}

// updated_at changes whenever the photo does, so the browser can cache each version for good
const imageUrl = (r) => `api/recipes/${r.id}/image?v=${r.updated_at}`;

const tagChips =(tags) => tags.map((t) => `<a class="chip" href="#/?tag=${encodeURIComponent(t)}">${esc(t)}</a>`).join("");

async function showList(params) {
  const q = params.get("q") || "", tag = params.get("tag") || "";
  view.innerHTML = `
    <div class="toolbar">
      <input id="search" type="search" placeholder="Søg i titler, ingredienser og tags" value="${esc(q)}">
      ${tag ? `<span class="chip on">${esc(tag)} <a href="#/" title="Fjern filter">×</a></span>` : ""}
      <a class="btn" href="#/import">Importér fra Mealie</a>
    </div>
    <div id="cards" class="cards"></div>`;
  const search = document.getElementById("search");
  let timer;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => render(search.value), 200);
  });
  async function render(text) {
    const list = await api(`recipes?${new URLSearchParams({ q: text, tag })}`);
    document.getElementById("cards").innerHTML = list.length
      ? list.map((r) => `
        <a class="card recipe" href="#/r/${r.id}">
          ${r.image ? `<img class="thumb" src="${imageUrl(r)}" alt="" loading="lazy">` : ""}
          <h3>${esc(r.title)}</h3>
          <p class="muted">${[r.minutes && `${r.minutes} min`, r.servings && `${r.servings} pers.`, ago(r.last_cooked)].filter(Boolean).join(" · ")}</p>
          <div>${r.tags.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
        </a>`).join("")
      : `<p class="empty">${q || tag ? "Ingen opskrifter matcher."
        : 'Ingen opskrifter endnu. <a href="#/new">Tilføj den første</a> eller <a href="#/import">importér fra Mealie</a>.'}</p>`;
  }
  render(q);
  search.focus();
}

async function showRecipe(id) {
  const r = await api(`recipes/${id}`);
  view.innerHTML = `
    <article class="card">
      ${r.image ? `<img class="hero" src="${imageUrl(r)}" alt="">` : ""}
      <div class="title-row">
        <h2>${esc(r.title)}</h2>
        <div class="actions">
          <button id="cooked" class="btn primary">Lavet i dag</button>
          <a class="btn" href="#/edit/${r.id}">Redigér</a>
        </div>
      </div>
      <p class="muted">${[r.minutes && `${r.minutes} min`, r.servings && `${r.servings} personer`,
        `${r.times_cooked} gange lavet`, ago(r.last_cooked)].filter(Boolean).join(" · ")}</p>
      ${r.description ? `<p>${esc(r.description)}</p>` : ""}
      <div>${tagChips(r.tags)}</div>
      <div class="columns">
        <section><h3>Ingredienser</h3><ul>${r.ingredients.map((i) => `<li>${esc(i)}</li>`).join("")}</ul></section>
        <section><h3>Fremgangsmåde</h3><ol>${r.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol></section>
      </div>
      ${r.source_url ? `<p class="muted">Kilde: <a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source_url)}</a></p>` : ""}
    </article>`;
  document.getElementById("cooked").onclick = async () => {
    await api(`recipes/${id}/cooked`, { method: "POST" });
    showRecipe(id);
  };
}

async function showForm(id) {
  const r = id ? await api(`recipes/${id}`) : { title: "", description: "", servings: "", minutes: "", ingredients: [], steps: [], tags: [], source_url: "" };
  view.innerHTML = `
    <form id="form" class="card form">
      <h2>${id ? "Redigér opskrift" : "Ny opskrift"}</h2>
      <label>Titel<input name="title" required value="${esc(r.title)}"></label>
      <label>Beskrivelse<textarea name="description" rows="2">${esc(r.description)}</textarea></label>
      <div class="row">
        <label>Personer<input name="servings" type="number" min="1" value="${esc(r.servings)}"></label>
        <label>Tid (min)<input name="minutes" type="number" min="1" value="${esc(r.minutes)}"></label>
      </div>
      <label>Ingredienser <span class="muted">(én pr. linje)</span><textarea name="ingredients" rows="8">${esc(r.ingredients.join("\n"))}</textarea></label>
      <label>Fremgangsmåde <span class="muted">(ét trin pr. linje)</span><textarea name="steps" rows="8">${esc(r.steps.join("\n"))}</textarea></label>
      <label>Tags <span class="muted">(adskilt med komma)</span><input name="tags" value="${esc(r.tags.join(", "))}"></label>
      <label>Kilde (link)<input name="source_url" type="url" value="${esc(r.source_url)}"></label>
      <div class="image-field">
        <span class="label">Billede</span>
        ${r.image ? `<img class="preview" src="${imageUrl(r)}" alt="">
          <label class="inline"><input type="checkbox" id="remove-image"> Fjern billedet</label>` : ""}
        <input type="file" id="image" accept="image/jpeg,image/png,image/webp,image/gif">
      </div>
      <p id="error" class="error" hidden></p>
      <div class="actions">
        <button class="btn primary" type="submit">Gem</button>
        <a class="btn" href="${id ? `#/r/${id}` : "#/"}">Annullér</a>
        ${id ? '<button id="delete" class="btn danger" type="button">Slet</button>' : ""}
      </div>
    </form>`;
  const form = document.getElementById("form");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const fields = Object.fromEntries(new FormData(form));
    delete fields.image;
    try {
      const saved = await api(id ? `recipes/${id}` : "recipes", { method: id ? "PUT" : "POST", body: JSON.stringify(fields) });
      const file = document.getElementById("image").files[0];
      if (file) await api(`recipes/${saved.id}/image`, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
      else if (document.getElementById("remove-image")?.checked) await api(`recipes/${saved.id}/image`, { method: "DELETE" });
      location.hash = `#/r/${saved.id}`;
    } catch (err) {
      const box = document.getElementById("error");
      box.textContent = err.message;
      box.hidden = false;
    }
  };
  if (id) {
    document.getElementById("delete").onclick = async () => {
      if (!confirm(`Slet "${r.title}"? Statistikken for opskriften bliver også slettet.`)) return;
      await api(`recipes/${id}`, { method: "DELETE" });
      location.hash = "#/";
    };
  }
}

function showImport() {
  view.innerHTML = `
    <div class="card form">
      <h2>Importér fra Mealie</h2>
      <p>Lav en backup i Mealie under <b>Indstillinger → Backups</b>, hent zip-filen og vælg den her.</p>
      <p class="muted">Opskrifter, ingredienser, fremgangsmåde, kategorier og tags, billeder og "lavede denne" kommer med.
        Opskrifter, der allerede findes, bliver sprunget over, så du kan importere den samme backup igen uden dubletter.</p>
      <input type="file" id="backup" accept=".zip,application/zip">
      <div class="actions"><button id="run" class="btn primary" disabled>Importér</button></div>
      <div id="result"></div>
    </div>`;
  const input = document.getElementById("backup"), run = document.getElementById("run"), out = document.getElementById("result");
  input.onchange = () => { run.disabled = !input.files.length; };
  run.onclick = async () => {
    run.disabled = true;
    out.innerHTML = '<p class="muted">Importerer …</p>';
    try {
      const r = await api("import/mealie", { method: "POST", body: input.files[0], headers: { "Content-Type": "application/zip" } });
      out.innerHTML = `
        <p><b>${r.imported}</b> opskrifter importeret med <b>${r.images}</b> billeder og <b>${r.cooked}</b> måltider i statistikken.</p>
        ${r.skipped.length ? `<p class="muted">Sprunget over, fordi de allerede findes: ${r.skipped.map(esc).join(", ")}</p>` : ""}
        ${r.image_errors.length ? `<p class="error">Billeder, der ikke kunne bruges: ${r.image_errors.map(esc).join(", ")}</p>` : ""}
        <p><a href="#/">Se opskrifterne</a></p>`;
    } catch (err) {
      out.innerHTML = `<p class="error">${esc(err.message)}</p>`;
      run.disabled = false;
    }
  };
}

// A list, not an object: objects sort number keys, which would put "Alt" (0) first
const RANGES = [[30, "30 dage"], [90, "90 dage"], [365, "1 år"], [0, "Alt"]];

async function showStats(params) {
  const days = Number(params.get("days") ?? 90);
  const s = await api(`stats?start=${days ? Math.floor(Date.now() / 1000) - days * 86400 : 0}`);
  const list = (rows, fn) => rows.length ? `<ol class="top">${rows.map(fn).join("")}</ol>` : '<p class="muted">Intet endnu.</p>';
  view.innerHTML = `
    <div class="toolbar seg">${RANGES.map(([d, label]) =>
      `<a href="#/stats?days=${d}" class="${d === days ? "on" : ""}">${label}</a>`).join("")}</div>
    <div class="kpis">
      <div class="card kpi"><b>${s.cooked}</b><span>måltider lavet</span></div>
      <div class="card kpi"><b>${s.distinct_recipes}</b><span>forskellige opskrifter</span></div>
      <div class="card kpi"><b>${s.recipes_total}</b><span>opskrifter i samlingen</span></div>
    </div>
    <div class="grid">
      <section class="card"><h3>Mest lavet</h3>${list(s.top, (r) => `<li><a href="#/r/${r.id}">${esc(r.title)}</a><span>${r.times}×</span></li>`)}</section>
      <section class="card"><h3>Populære tags</h3>${list(s.tags, (t) => `<li><a href="#/?tag=${encodeURIComponent(t.tag)}">${esc(t.tag)}</a><span>${t.times}×</span></li>`)}</section>
      <section class="card"><h3>Seneste måltider</h3>${list(s.recent, (r) => `<li><a href="#/r/${r.id}">${esc(r.title)}</a><span>${date(r.cooked_at)}${r.user_name ? ` · ${esc(r.user_name)}` : ""}</span></li>`)}</section>
      <section class="card"><h3>Længe siden</h3>${list(s.forgotten, (r) => `<li><a href="#/r/${r.id}">${esc(r.title)}</a><span>${ago(r.last_cooked)}</span></li>`)}</section>
    </div>`;
}

async function route() {
  const [path, query = ""] = location.hash.slice(1).split("?");
  const params = new URLSearchParams(query);
  const parts = (path || "/").split("/").filter(Boolean);
  const active = parts[0] === "stats" ? "stats" : parts[0] === "new" ? "new" : parts.length ? "" : "list";
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.view === active));
  try {
    if (parts[0] === "r") await showRecipe(parts[1]);
    else if (parts[0] === "edit") await showForm(parts[1]);
    else if (parts[0] === "new") await showForm(null);
    else if (parts[0] === "stats") await showStats(params);
    else if (parts[0] === "import") showImport();
    else await showList(params);
  } catch (err) {
    view.innerHTML = `<p class="empty">Noget gik galt: ${esc(err.message)}</p>`;
  }
}

window.addEventListener("hashchange", route);
route();
