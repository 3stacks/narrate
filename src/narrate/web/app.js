const $ = (id) => document.getElementById(id);

const state = {
  meta: null,
  file: null,
  preview: null,
};

async function boot() {
  const meta = await (await fetch("/api/meta")).json();
  state.meta = meta;
  const badge = $("key-badge");
  badge.textContent = meta.has_key ? "OpenRouter ready" : "missing API key";
  badge.className = "badge " + (meta.has_key ? "ok" : "bad");

  const list = $("who-list");
  list.innerHTML = "";
  meta.users.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    list.appendChild(opt);
  });
  $("who").value = meta.users[0] || "";

  const modelSel = $("model");
  modelSel.innerHTML = "";
  meta.models.forEach((model) => {
    const opt = document.createElement("option");
    opt.value = model.id;
    opt.textContent = `${model.label}  ·  $${model.usd_per_million_chars}/M chars`;
    if (model.id === meta.default_model) opt.selected = true;
    modelSel.appendChild(opt);
  });
  fillVoices();
  modelSel.addEventListener("change", () => {
    fillVoices();
    if (state.file) previewFile(state.file);
  });
  $("file").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) previewFile(file);
  });
  const drop = $("drop");
  drop.addEventListener("dragover", (event) => {
    event.preventDefault();
    drop.classList.add("over");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (event) => {
    event.preventDefault();
    drop.classList.remove("over");
    const file = event.dataTransfer.files[0];
    if (file) previewFile(file);
  });
  $("go").addEventListener("click", enqueue);
  refreshJobs();
  setInterval(refreshJobs, 2500);
}

function currentModel() {
  return state.meta.models.find((model) => model.id === $("model").value);
}

function fillVoices() {
  const model = currentModel();
  const voiceSel = $("voice");
  voiceSel.innerHTML = "";
  if (!model) return;
  $("model-notes").textContent = model.notes;
  const preferred = model.id === state.meta.default_model
    ? state.meta.default_voice
    : model.default_voice;
  model.voices.forEach((voice) => {
    const opt = document.createElement("option");
    opt.value = voice;
    opt.textContent = voice;
    if (voice === preferred) opt.selected = true;
    voiceSel.appendChild(opt);
  });
}

async function previewFile(file) {
  state.file = file;
  $("file-name").textContent = file.name;
  $("form").classList.remove("hidden");
  $("go").disabled = true;
  $("go").textContent = "Reading book…";
  const body = new FormData();
  body.append("file", file);
  body.append("model", $("model").value);
  const response = await fetch("/api/preview", { method: "POST", body });
  const data = await response.json();
  if (!response.ok) {
    $("preview").classList.remove("hidden");
    $("book-title").textContent = "Could not read that file";
    $("book-author").textContent = data.detail || "Unknown error";
    $("go").textContent = "Generate audiobook";
    return;
  }
  state.preview = data;
  $("preview").classList.remove("hidden");
  $("book-title").textContent = data.title;
  $("book-author").textContent = data.author;
  $("stat-chapters").textContent = data.chapter_count;
  $("stat-chars").textContent = data.chars.toLocaleString();
  $("stat-cost").textContent = `$${Number(data.estimated_usd).toFixed(2)}`;
  $("book-warning").textContent = data.warning || "";
  const list = $("chapter-list");
  list.innerHTML = "";
  data.chapters.forEach((chapter) => {
    const item = document.createElement("li");
    item.textContent = `${chapter.title}  ·  ${chapter.chars.toLocaleString()} chars`;
    list.appendChild(item);
  });
  $("go").disabled = !state.meta.has_key;
  $("go").textContent = state.meta.has_key
    ? `Generate for about $${Number(data.estimated_usd).toFixed(2)}`
    : "Set OPENROUTER_API_KEY first";
}

async function enqueue() {
  if (!state.file) return;
  $("go").disabled = true;
  const body = new FormData();
  body.append("file", state.file);
  body.append("who", $("who").value);
  body.append("model", $("model").value);
  body.append("voice", $("voice").value);
  const response = await fetch("/api/jobs", { method: "POST", body });
  const data = await response.json();
  if (!response.ok) {
    alert(data.detail || "Could not queue the book");
    $("go").disabled = false;
    return;
  }
  $("go").textContent = `Queued as job ${data.id}`;
  refreshJobs();
}

async function refreshJobs() {
  const response = await fetch("/api/jobs");
  if (!response.ok) return;
  const data = await response.json();
  const root = $("jobs");
  root.innerHTML = "";
  if (!data.jobs.length) {
    root.innerHTML = '<p class="hint">Nothing in the queue yet.</p>';
    return;
  }
  data.jobs.forEach((job) => {
    const el = document.createElement("article");
    el.className = `job ${job.status}`;
    const pct = job.chunk_total
      ? Math.round((job.chunk_done / job.chunk_total) * 100)
      : job.status === "done"
        ? 100
        : 0;
    el.innerHTML = `
      <header>
        <h3>${escapeHtml(job.title || job.source_name)}</h3>
        <span class="badge">${job.status}</span>
      </header>
      <p class="meta">${escapeHtml(job.author || "")} · imported by ${escapeHtml(job.importer)} · about $${Number(job.estimated_usd).toFixed(2)}</p>
      <p class="meta">${job.chapter_done}/${job.chapter_count} chapters · ${job.chunk_done}/${job.chunk_total} chunks</p>
      ${job.error ? `<p class="warn">${escapeHtml(job.error)}</p>` : ""}
      <div class="bar"><i style="width:${pct}%"></i></div>
    `;
    if (job.status === "error") {
      const retry = document.createElement("button");
      retry.textContent = "Retry";
      retry.addEventListener("click", async () => {
        await fetch(`/api/jobs/${job.id}/retry`, { method: "POST" });
        refreshJobs();
      });
      el.appendChild(retry);
    }
    root.appendChild(el);
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

boot().catch((err) => {
  $("key-badge").textContent = "UI failed to load";
  $("key-badge").className = "badge bad";
  console.error(err);
});
