const PREVIEW_LIMIT = 60;
const POLL_INTERVAL = 1500;

const $ = (id) => document.getElementById(id);

let pollingNull;
let loginPollingNull;

const form = $("searchForm");
const searchBtn = $("searchBtn");
const authBanner = $("authBanner");
const progressCard = $("progressCard");
const statusMessage = $("statusMessage");
const currentPageEl = $("currentPage");
const foundEl = $("found");
const progressFill = $("progressFill");
const errorBox = $("errorBox");
const resultCard = $("resultSection");
const downloadBtn = $("downloadBtn");
const driveBtn = $("driveBtn");
const previewNote = $("previewNote");
const resultsBody = $("resultsBody");
const maxPagesInput = $("maxPages");
const allPagesCheckbox = $("allPages");

allPagesCheckbox.addEventListener("change", () => {
  maxPagesInput.disabled = allPagesCheckbox.checked;
});

function setError(message) {
  if (!message) {
    errorBox.classList.add("hidden");
    errorBox.textContent = "";
    return;
  }
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function makeLoginBanner() {
  authBanner.className = "banner banner-warn";
  authBanner.innerHTML =
    "Para buscar en Lusha necesitas una sesión activa. " +
    "Haz clic en el botón, inicia sesión en la ventana del navegador que se abre y la sesión quedará guardada. " +
    "<button type='button' id='loginBtn' class='btn-secondary'>Iniciar sesión en Lusha</button>";
  authBanner.classList.remove("hidden");
  $("loginBtn").addEventListener("click", startLogin);
}

function renderAuthStatus(data) {
  if (data.login_running) {
    authBanner.textContent = "Esperando a que completes el inicio de sesión en la ventana del navegador...";
    authBanner.classList.remove("hidden");
    return;
  }
  if (data.last_result && data.last_result.ok === false) {
    authBanner.textContent = "Error al iniciar sesión: " + data.last_result.error;
    authBanner.classList.remove("hidden");
  } else if (data.logged_in) {
    authBanner.textContent = "Sesión de Lusha activa.";
    authBanner.className = "banner banner-ok";
    authBanner.classList.remove("hidden");
  } else {
    makeLoginBanner();
  }
}

async function getAuthStatus() {
  try {
    const res = await fetch("/api/auth/status");
    return await res.json();
  } catch {
    return null;
  }
}

async function refreshAuth() {
  const data = await getAuthStatus();
  if (data) renderAuthStatus(data);
}

function startLogin() {
  fetch("/api/login", { method: "POST" })
    .then(() => pollLogin())
    .catch(() => setError("No se pudo iniciar el proceso de login."));
}

function pollLogin() {
  clearInterval(loginPollingNull);
  loginPollingNull = setInterval(async () => {
    const data = await getAuthStatus();
    if (!data) return;
    if (!data.login_running) {
      clearInterval(loginPollingNull);
      renderAuthStatus(data);
      if (data.logged_in) setError(null);
    } else {
      renderAuthStatus(data);
    }
  }, 1500);
}

function renderTable(job) {
  const results = job.results || [];
  resultsBody.innerHTML = "";
  const fragment = document.createDocumentFragment();
  const shown = Math.min(results.length, PREVIEW_LIMIT);
  results.slice(0, shown).forEach((row) => {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = row.name || "-";
    const role = document.createElement("td");
    role.textContent = row.role || "-";
    const url = document.createElement("td");
    if (row.url) {
      const a = document.createElement("a");
      a.href = row.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = row.url;
      url.appendChild(a);
    } else {
      url.textContent = "-";
    }
    tr.append(name, role, url);
    fragment.appendChild(tr);
  });
  resultsBody.appendChild(fragment);

  if (results.length > PREVIEW_LIMIT) {
    previewNote.textContent =
      "Mostrando los primeros " + PREVIEW_LIMIT + " de " + results.length + " resultados.";
  } else {
    previewNote.textContent = "";
  }
}

function renderJob(job) {
  statusMessage.textContent = job.message || job.status;
  currentPageEl.textContent = job.current_page || 0;
  foundEl.textContent = job.found || 0;

  if (job.all_pages) {
    progressFill.classList.add("indeterminate");
    progressFill.style.width = "";
  } else {
    progressFill.classList.remove("indeterminate");
    progressFill.style.width = Math.min(100, ((job.current_page || 0) / (job.max_pages || 1)) * 100) + "%";
  }

  if (job.status === "running" || job.status === "pending") {
    renderTable(job);
  } else if (job.status === "done") {
    clearInterval(pollingNull);
    progressFill.classList.remove("indeterminate");
    progressFill.style.width = "100%";
    renderTable(job);
    resultCard.classList.remove("hidden");
    downloadBtn.href = "/api/jobs/" + job.id + "/download";
    downloadBtn.classList.remove("hidden");
    if (job.drive_url) {
      driveBtn.href = job.drive_url;
      driveBtn.classList.remove("hidden");
    } else {
      driveBtn.classList.add("hidden");
    }
    searchBtn.disabled = false;
    searchBtn.classList.remove("btn-disabled");
    searchBtn.textContent = "Buscar contactos";
  } else if (job.status === "needs_login") {
    clearInterval(pollingNull);
    resultCard.classList.add("hidden");
    setError(job.error);
    makeLoginBanner();
    searchBtn.disabled = false;
    searchBtn.classList.remove("btn-disabled");
    searchBtn.textContent = "Buscar contactos";
  } else if (job.status === "error") {
    clearInterval(pollingNull);
    setError(job.error || "Ocurrió un error inesperado.");
    searchBtn.disabled = false;
    searchBtn.classList.remove("btn-disabled");
    searchBtn.textContent = "Buscar contactos";
  }
}

function startJob(jobId) {
  resultCard.classList.add("hidden");
  progressCard.classList.remove("hidden");
  clearInterval(pollingNull);
  pollingNull = setInterval(async () => {
    try {
      const res = await fetch("/api/jobs/" + jobId);
      if (!res.ok) {
        clearInterval(pollingNull);
        setError("No se pudo obtener el estado del proceso.");
        return;
      }
      renderJob(await res.json());
    } catch {
      clearInterval(pollingNull);
      setError("Error de conexión con el servidor.");
    }
  }, POLL_INTERVAL);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setError(null);

  const auth = await getAuthStatus();
  if (!auth || !auth.logged_in) {
    setError("Necesitas iniciar sesión en Lusha antes de buscar.");
    refreshAuth();
    return;
  }

  const company = $("company").value.trim();
  const maxPages = parseInt(maxPagesInput.value, 10) || 10;
  const departmentsRaw = $("departments").value
    .split(/[,\n]/)
    .map((d) => d.trim())
    .filter(Boolean);
  const senioritiesRaw = $("seniorities").value
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const countriesRaw = $("countries").value
    .split(/[,\n]/)
    .map((c) => c.trim())
    .filter(Boolean);
  const payload = {
    company,
    filters: {
      departments: departmentsRaw,
      seniorities: senioritiesRaw,
      countries: countriesRaw,
    },
  };
  if (allPagesCheckbox.checked) {
    payload.all_pages = true;
  } else {
    payload.max_pages = maxPages;
  }

  searchBtn.disabled = true;
  searchBtn.classList.add("btn-disabled");
  searchBtn.textContent = "Buscando...";

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "La búsqueda falló.");
    }
    progressCard.classList.remove("hidden");
    startJob(data.job_id);
  } catch (error) {
    searchBtn.disabled = false;
    searchBtn.classList.remove("btn-disabled");
    searchBtn.textContent = "Buscar contactos";
    setError(error.message);
  }
});

refreshAuth();