const $ = (id) => document.getElementById(id);
let edicion = null;
let seccionActiva = "Todas";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function enlaces(n) {
  return `<div class="enlaces">${n.enlaces
    .map((e) => `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.medio)}</a>`)
    .join("")}</div>`;
}

function etiqueta(n) {
  return `<span class="etiqueta${n.importancia >= 5 ? " importante" : ""}">${esc(n.seccion)}</span>`;
}

function pintar() {
  const todas = edicion.noticias;
  const visibles = seccionActiva === "Todas" ? todas : todas.filter((n) => n.seccion === seccionActiva);
  const [primera, ...resto] = seccionActiva === "Todas" ? visibles : [...visibles].sort((a, b) => b.importancia - a.importancia);

  $("destacada").innerHTML = primera
    ? `${etiqueta(primera)}<h2>${esc(primera.titulo)}</h2><p>${esc(primera.resumen)}</p>${enlaces(primera)}`
    : `<p class="vacio">No hay noticias en esta sección hoy.</p>`;

  const ordenadas = seccionActiva === "Todas" ? [...resto].sort((a, b) => b.importancia - a.importancia) : resto;
  $("lista").innerHTML = ordenadas
    .map((n) => `<article class="nota">${etiqueta(n)}<h3>${esc(n.titulo)}</h3><p>${esc(n.resumen)}</p>${enlaces(n)}</article>`)
    .join("");
}

function pintarSecciones() {
  const presentes = [...new Set(edicion.noticias.map((n) => n.seccion))];
  if (!presentes.includes(seccionActiva)) seccionActiva = "Todas";
  $("secciones").innerHTML = ["Todas", ...presentes]
    .map((s) => `<button type="button" aria-pressed="${s === seccionActiva}">${esc(s)}</button>`)
    .join("");
  $("secciones").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      seccionActiva = b.textContent;
      pintarSecciones();
      pintar();
    })
  );
}

async function cargar(fecha) {
  const ruta = fecha ? `data/archivo/${fecha}.json` : "data/noticias.json";
  try {
    const r = await fetch(`${ruta}?v=${Date.now()}`);
    if (!r.ok) throw new Error(r.status);
    edicion = await r.json();
  } catch {
    $("fecha").textContent = "No se pudo cargar la edición.";
    return;
  }
  const f = new Date(edicion.actualizado);
  $("fecha").textContent =
    f.toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) +
    " · actualizado " +
    f.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" });
  $("pie-medios").textContent = `Fuentes de esta edición: ${edicion.medios.join(", ")}.`;
  pintarSecciones();
  pintar();
}

async function cargarArchivo() {
  try {
    const fechas = await (await fetch(`data/archivo.json?v=${Date.now()}`)).json();
    fechas.slice(1, 31).forEach((d) => $("archivo").insertAdjacentHTML("beforeend", `<option value="${esc(d)}">${esc(d)}</option>`));
  } catch {}
  $("archivo").addEventListener("change", (e) => cargar(e.target.value));
}

cargar();
cargarArchivo();
