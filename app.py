import streamlit as st
import json
import os
import hashlib
import io
import base64
import pandas as pd
from datetime import date
from PIL import Image, ImageOps

# Configuración principal de la app
st.set_page_config(page_title="Sistema de Inspección de Tolvas CAT", layout="wide")

st.title("📋 Reporte de Inspección de Tolvas CAT 794 AC")

# --- COMPONENTE DE ANOTACIÓN DE FOTOS (Streamlit Components v2) ---
# Se registra UNA sola vez a nivel de módulo. Todo vive en este mismo
# archivo (sin carpetas ni paquetes externos), y permite recibir de vuelta
# la imagen anotada directamente, sin pasos de descargar/subir.
_ANOTADOR_HTML = """
<div>
  <div id="barra" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px;">
    <button data-tool="none" class="sel">🚫 Ninguno</button>
    <button data-tool="circle">⭕ Círculo</button>
    <button data-tool="rect">🔲 Rectángulo</button>
    <button data-tool="line">↗️ Flecha</button>
    <button data-tool="freedraw">✏️ Libre</button>
    <button id="deshacer">↩️ Deshacer</button>
    <button id="limpiar">🗑️ Borrar todo</button>
    <button id="guardar" class="guardar">💾 Guardar anotación</button>
  </div>
  <canvas id="lienzo" width="600" height="450"></canvas>
  <div id="estado"></div>
</div>
"""

_ANOTADOR_CSS = """
#barra button {
  background:#262730; color:#fafafa; border:1px solid #555; border-radius:6px;
  padding:7px 10px; font-size:13px; cursor:pointer;
}
#barra button:hover { background:#3a3b45; }
#barra button.sel { background:#FF4B4B; border-color:#FF4B4B; }
#barra button.guardar { background:#21c45d; border-color:#21c45d; font-weight:bold; }
canvas { border:1px solid #444; width:100%; height:auto; touch-action:none; display:block; }
#estado { font-size:12px; color:#9a9a9a; margin-top:4px; }
"""

_ANOTADOR_JS = """
export default function(component) {
  const { data, parentElement, setStateValue } = component;

  if (!parentElement._anotadorInit) {
    parentElement._anotadorInit = true;
    parentElement._formas = [];
    parentElement._herramienta = "none";
    parentElement._imagenFondo = null;

    const canvas = parentElement.querySelector('#lienzo');
    const ctx = canvas.getContext('2d');
    const estadoEl = parentElement.querySelector('#estado');

    function redibujar() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (parentElement._imagenFondo) ctx.drawImage(parentElement._imagenFondo, 0, 0, canvas.width, canvas.height);
      const todas = parentElement._formas.concat(parentElement._formaActual ? [parentElement._formaActual] : []);
      todas.forEach(dibujarForma);
    }
    function dibujarForma(f) {
      if (!f) return;
      ctx.lineWidth = 3; ctx.strokeStyle = "#FF0000"; ctx.fillStyle = "rgba(255,0,0,0.2)";
      if (f.tipo === "circle") {
        const cx=(f.x1+f.x2)/2, cy=(f.y1+f.y2)/2, rx=Math.abs(f.x2-f.x1)/2, ry=Math.abs(f.y2-f.y1)/2;
        ctx.beginPath(); ctx.ellipse(cx,cy,rx,ry,0,0,2*Math.PI); ctx.fill(); ctx.stroke();
      } else if (f.tipo === "rect") {
        ctx.beginPath(); ctx.rect(f.x1,f.y1,f.x2-f.x1,f.y2-f.y1); ctx.fill(); ctx.stroke();
      } else if (f.tipo === "line") {
        const ang = Math.atan2(f.y2-f.y1, f.x2-f.x1);
        ctx.beginPath(); ctx.moveTo(f.x1,f.y1); ctx.lineTo(f.x2,f.y2); ctx.stroke();
        const t=12;
        ctx.beginPath(); ctx.moveTo(f.x2,f.y2);
        ctx.lineTo(f.x2-t*Math.cos(ang-Math.PI/6), f.y2-t*Math.sin(ang-Math.PI/6));
        ctx.lineTo(f.x2-t*Math.cos(ang+Math.PI/6), f.y2-t*Math.sin(ang+Math.PI/6));
        ctx.closePath(); ctx.fillStyle="#FF0000"; ctx.fill();
      } else if (f.tipo === "freedraw") {
        ctx.beginPath();
        f.puntos.forEach((p,i)=> i===0 ? ctx.moveTo(p.x,p.y) : ctx.lineTo(p.x,p.y));
        ctx.stroke();
      }
    }
    function coords(ev) {
      const r = canvas.getBoundingClientRect();
      const ex = ev.touches ? ev.touches[0].clientX : ev.clientX;
      const ey = ev.touches ? ev.touches[0].clientY : ev.clientY;
      return { x: (ex-r.left)*(canvas.width/r.width), y: (ey-r.top)*(canvas.height/r.height) };
    }
    function iniciar(ev) {
      if (parentElement._herramienta === "none") return; // no bloquea el deslizar/scroll
      ev.preventDefault();
      parentElement._dibujando = true;
      const {x,y} = coords(ev);
      parentElement._formaActual = parentElement._herramienta === "freedraw"
        ? {tipo:"freedraw",puntos:[{x,y}]}
        : {tipo:parentElement._herramienta,x1:x,y1:y,x2:x,y2:y};
    }
    function mover(ev) {
      if (!parentElement._dibujando) return;
      ev.preventDefault();
      const {x,y} = coords(ev);
      if (parentElement._herramienta === "freedraw") parentElement._formaActual.puntos.push({x,y});
      else { parentElement._formaActual.x2 = x; parentElement._formaActual.y2 = y; }
      redibujar();
    }
    function terminar() {
      if (!parentElement._dibujando) return;
      parentElement._dibujando = false;
      if (parentElement._formaActual) parentElement._formas.push(parentElement._formaActual);
      parentElement._formaActual = null;
      redibujar();
      estadoEl.textContent = "Sin guardar todavía";
    }

    canvas.addEventListener("mousedown", iniciar);
    canvas.addEventListener("mousemove", mover);
    window.addEventListener("mouseup", terminar);
    canvas.addEventListener("touchstart", iniciar, {passive:false});
    canvas.addEventListener("touchmove", mover, {passive:false});
    canvas.addEventListener("touchend", terminar);

    parentElement.querySelectorAll('#barra button[data-tool]').forEach((btn) => {
      btn.addEventListener("click", () => {
        parentElement.querySelectorAll('#barra button[data-tool]').forEach((b) => b.classList.remove("sel"));
        btn.classList.add("sel");
        parentElement._herramienta = btn.dataset.tool;
      });
    });
    parentElement.querySelector('#deshacer').addEventListener("click", () => { parentElement._formas.pop(); redibujar(); });
    parentElement.querySelector('#limpiar').addEventListener("click", () => { parentElement._formas = []; redibujar(); });
    parentElement.querySelector('#guardar').addEventListener("click", () => {
      setStateValue('imagen_anotada', canvas.toDataURL('image/png'));
      estadoEl.textContent = "✅ Anotación guardada";
    });

    parentElement._redibujar = redibujar;
  }

  if (data && data.imagen_base64 && parentElement._ultimaImagen !== data.imagen_base64) {
    parentElement._ultimaImagen = data.imagen_base64;
    const canvasEl = parentElement.querySelector('#lienzo');
    const img = new Image();
    img.onload = () => {
      // El lienzo toma EXACTAMENTE el ancho y alto reales de la foto,
      // para que nunca se vea estirada/aplastada (antes era un tamaño fijo).
      canvasEl.width = img.naturalWidth;
      canvasEl.height = img.naturalHeight;
      parentElement._imagenFondo = img;
      parentElement._redibujar();
    };
    img.src = "data:image/png;base64," + data.imagen_base64;
  }
}
"""

_componente_anotador = st.components.v2.component(
    "anotador_fotos_tolva",
    html=_ANOTADOR_HTML,
    css=_ANOTADOR_CSS,
    js=_ANOTADOR_JS,
)


def anotador_fotos(imagen_base64_sin_prefijo, key):
    """
    Muestra el lienzo de anotación para una foto y devuelve la imagen ya
    anotada (string base64) en cuanto el usuario presiona "Guardar
    anotación". Devuelve None mientras no se haya guardado.
    """
    resultado = _componente_anotador(
        data={"imagen_base64": imagen_base64_sin_prefijo},
        key=key,
        on_imagen_anotada_change=lambda: None
    )
    return resultado.imagen_anotada if resultado else None


# --- COMPONENTE DE CÁMARA CON ZOOM NATIVO ---
# Reemplaza el widget estándar st.camera_input (que no permite zoom) por una
# cámara propia con control de zoom real de hardware (cuando el navegador lo
# soporta) y respaldo con pellizco/deslizador para acercar digitalmente.
_CAMARA_HTML = """
<div>
  <video id="video" autoplay playsinline muted></video>
  <div id="controlesZoom" style="display:none;">
    <span>🔍</span>
    <input type="range" id="zoomSlider" min="1" max="8" step="0.1" value="1">
    <span id="zoomValor">1.0x</span>
  </div>
  <div style="display:flex;gap:8px;margin-top:8px;">
    <button id="btnCapturar" class="capturar">📸 Capturar Foto</button>
  </div>
  <div id="estadoCam" style="font-size:12px;color:#9a9a9a;margin-top:4px;"></div>
</div>
"""

_CAMARA_CSS = """
video { width:100%; border-radius:8px; background:#000; touch-action:none; display:block; }
#controlesZoom { display:flex; align-items:center; gap:8px; margin-top:6px; color:#fafafa; font-size:13px; }
#controlesZoom input[type=range] { flex:1; }
button.capturar {
  background:#21c45d; color:#fff; border:none; border-radius:6px;
  padding:10px 16px; font-size:14px; font-weight:bold; cursor:pointer;
}
"""

_CAMARA_JS = """
export default function(component) {
  const { parentElement, setStateValue } = component;
  if (parentElement._camInit) return;
  parentElement._camInit = true;

  const video = parentElement.querySelector('#video');
  const estadoEl = parentElement.querySelector('#estadoCam');
  const controlesZoom = parentElement.querySelector('#controlesZoom');
  const zoomSlider = parentElement.querySelector('#zoomSlider');
  const zoomValor = parentElement.querySelector('#zoomValor');
  let track = null;
  let usaZoomHardware = false;
  let zoomDigital = 1;

  navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
    audio: false
  }).then((stream) => {
    video.srcObject = stream;
    track = stream.getVideoTracks()[0];
    const capacidades = track.getCapabilities ? track.getCapabilities() : {};
    if (capacidades.zoom) {
      usaZoomHardware = true;
      zoomSlider.min = capacidades.zoom.min;
      zoomSlider.max = capacidades.zoom.max;
      zoomSlider.step = capacidades.zoom.step || 0.1;
      zoomSlider.value = capacidades.zoom.min;
      controlesZoom.style.display = "flex";
    } else {
      // Respaldo: zoom digital con CSS si el navegador no expone zoom de hardware
      controlesZoom.style.display = "flex";
    }
    estadoEl.textContent = "Cámara lista";
  }).catch((err) => {
    estadoEl.textContent = "⚠️ No se pudo abrir la cámara: " + err.message;
  });

  function aplicarZoom(valor) {
    if (usaZoomHardware && track) {
      track.applyConstraints({ advanced: [{ zoom: parseFloat(valor) }] }).catch(() => {});
    } else {
      zoomDigital = parseFloat(valor);
      video.style.transform = "scale(" + zoomDigital + ")";
    }
    zoomValor.textContent = parseFloat(valor).toFixed(1) + "x";
  }
  zoomSlider.addEventListener("input", (ev) => aplicarZoom(ev.target.value));

  // Pellizco con dos dedos sobre la vista previa
  let distanciaInicial = null, zoomInicial = 1;
  video.addEventListener("touchstart", (ev) => {
    if (ev.touches.length === 2) {
      distanciaInicial = Math.hypot(
        ev.touches[0].clientX - ev.touches[1].clientX,
        ev.touches[0].clientY - ev.touches[1].clientY
      );
      zoomInicial = parseFloat(zoomSlider.value);
    }
  }, { passive: true });
  video.addEventListener("touchmove", (ev) => {
    if (ev.touches.length === 2 && distanciaInicial) {
      const distanciaActual = Math.hypot(
        ev.touches[0].clientX - ev.touches[1].clientX,
        ev.touches[0].clientY - ev.touches[1].clientY
      );
      const factor = distanciaActual / distanciaInicial;
      let nuevoZoom = zoomInicial * factor;
      const min = parseFloat(zoomSlider.min), max = parseFloat(zoomSlider.max);
      nuevoZoom = Math.max(min, Math.min(max, nuevoZoom));
      zoomSlider.value = nuevoZoom;
      aplicarZoom(nuevoZoom);
    }
  }, { passive: true });

  parentElement.querySelector('#btnCapturar').addEventListener("click", () => {
    const lienzoCaptura = document.createElement("canvas");
    if (usaZoomHardware || zoomDigital === 1) {
      lienzoCaptura.width = video.videoWidth;
      lienzoCaptura.height = video.videoHeight;
      lienzoCaptura.getContext("2d").drawImage(video, 0, 0);
    } else {
      // Recorta digitalmente la zona ampliada (zoom digital de respaldo)
      const anchoRecorte = video.videoWidth / zoomDigital;
      const altoRecorte = video.videoHeight / zoomDigital;
      const x = (video.videoWidth - anchoRecorte) / 2;
      const y = (video.videoHeight - altoRecorte) / 2;
      lienzoCaptura.width = anchoRecorte;
      lienzoCaptura.height = altoRecorte;
      lienzoCaptura.getContext("2d").drawImage(video, x, y, anchoRecorte, altoRecorte, 0, 0, anchoRecorte, altoRecorte);
    }
    const resultado = lienzoCaptura.toDataURL("image/jpeg", 0.92);
    setStateValue("foto_capturada", resultado);
    estadoEl.textContent = "✅ Foto capturada";
    if (track) track.stop();
  });
}
"""

_componente_camara = st.components.v2.component(
    "camara_nativa_tolva",
    html=_CAMARA_HTML,
    css=_CAMARA_CSS,
    js=_CAMARA_JS,
)


def camara_nativa(key):
    """
    Cámara propia con zoom (usa el zoom de hardware del celular cuando el
    navegador lo permite; si no, hace zoom digital con pellizco/deslizador).
    Devuelve la foto capturada (string base64 con prefijo data:image/jpeg)
    o None mientras no se haya capturado nada.
    """
    resultado = _componente_camara(key=key, on_foto_capturada_change=lambda: None)
    return resultado.foto_capturada if resultado else None


def redimensionar_conservando_calidad(img, max_lado=1400):
    """
    Redimensiona una foto manteniendo su proporción original (nunca la
    distorsiona) y sin agrandar fotos pequeñas. max_lado controla el lado
    más largo de la foto final: 1400px conserva buena nitidez para revisar
    defectos, sin generar archivos gigantes que hagan lenta la app.
    """
    ancho, alto = img.size
    escala = min(max_lado / max(ancho, alto), 1.0)
    if escala >= 1.0:
        return img
    nuevo_ancho = max(1, int(ancho * escala))
    nuevo_alto = max(1, int(alto * escala))
    return img.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)


def mostrar_imagen_responsive(ruta_o_objeto, caption=None):
    """
    Muestra una imagen a ancho completo sin importar la version de Streamlit
    instalada (el nombre del parametro para 'ancho completo' ha cambiado
    varias veces entre versiones de Streamlit: use_column_width ->
    use_container_width -> width='stretch'). Se prueba cada opcion en orden
    hasta que una funcione.
    """
    try:
        st.image(ruta_o_objeto, caption=caption, width="stretch")
    except TypeError:
        try:
            st.image(ruta_o_objeto, caption=caption, use_container_width=True)
        except TypeError:
            try:
                st.image(ruta_o_objeto, caption=caption, use_column_width=True)
            except TypeError:
                st.image(ruta_o_objeto, caption=caption)

# --- BASE DE DATOS LOCAL PARA RECORDAR TOLVA ---
DB_FILE = os.path.join("base_datos", "tolvas_db.json")

def cargar_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def guardar_db(data):
    os.makedirs("base_datos", exist_ok=True)
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

db_tolvas = cargar_db()

# --- SECCIÓN 1: ENCABEZADO ---
st.header("1. Datos Generales del Informe")

col1, col2, col3 = st.columns(3)

with col1:
    opc_cliente = st.selectbox("Cliente:", ["ANGLOAMERICAN QUELLAVECO S.A.", "[Entrada Manual]"], key="header_cliente_select")
    cliente = st.text_input("Nombre del Cliente:", value="ANGLOAMERICAN QUELLAVECO S.A.", key="header_cliente_input") if opc_cliente == "[Entrada Manual]" else opc_cliente

    opc_lugar = st.selectbox("Lugar:", ["TRUCK SHOP", "[Entrada Manual]"], key="header_lugar_select")
    lugar = st.text_input("Lugar de Inspección:", value="TRUCK SHOP", key="header_lugar_input") if opc_lugar == "[Entrada Manual]" else opc_lugar

    fecha_insp = st.date_input("Fecha de Inspección:", value=date.today(), key="header_fecha")

with col2:
    lista_equipos = [f"HT{str(i).zfill(3)}" for i in range(1, 35)]
    cod_equipo = st.selectbox("Código de Equipo:", lista_equipos, index=1, key="header_equipo")

    tolva_recordada = db_tolvas.get(cod_equipo, "T-CA2" if cod_equipo == "HT002" else "")
    cod_tolva = st.text_input("Código de Tolva:", value=tolva_recordada, key="header_tolva")

    if cod_tolva and cod_tolva != db_tolvas.get(cod_equipo):
        db_tolvas[cod_equipo] = cod_tolva
        guardar_db(db_tolvas)

    horometro = st.number_input("Horómetro (hrs):", value=34876.3, step=0.1, format="%.1f", key="header_horometro")

with col3:
    sufijo_informe = st.text_input("Sufijo del Informe (XXX):", value="023", key="header_sufijo")
    cod_informe = f"ZA-IF-{cod_equipo}-{sufijo_informe}"
    st.info(f"Código Generado: **{cod_informe}**")

    revision = st.text_input("Revisión:", value="00", key="header_revision")
    pm = st.selectbox("Mantenimiento (PM):", ["500H", "1000H", "1500H", "2000H"], key="header_pm")

st.markdown("---")

# --- SECCIÓN MEDICIÓN DE ESPESORES (Solo en 1000H y 2000H) ---
if pm in ["1000H", "2000H"]:
    st.header("📏 Mapeo / Medición de Espesores (Matriz 8x7)")
    no_medicion = st.checkbox("⚠️ Marcar como 'NO SE REALIZÓ MEDICIÓN DE ESPESORES'", key="check_no_medicion")

    if no_medicion:
        st.warning("Se ha seleccionado omitir la medición. El reporte se llenará con '-' y agregará la nota explicativa.")
        matriz_espesores_df = pd.DataFrame([["-"]*7 for _ in range(8)], 
                                    index=[f"Punto {i+1}" for i in range(8)],
                                    columns=[f"Eje {j+1}" for j in range(7)])
        st.dataframe(matriz_espesores_df, use_container_width=True)
    else:
        st.caption("Ingrese manualmente las lecturas de ultrasonido (mm) en la matriz:")
        df_init_espesores = pd.DataFrame([[20.00]*7 for _ in range(8)], 
                               index=[f"Punto {i+1}" for i in range(8)],
                               columns=[f"Eje {j+1}" for j in range(7)])
        
        column_config_espesores = {
            f"Eje {i+1}": st.column_config.NumberColumn(width=65, format="%.2f") for i in range(7)
        }

        matriz_espesores_editada = st.data_editor(
            df_init_espesores, 
            use_container_width=False,
            column_config=column_config_espesores,
            key="editor_espesores"
        )

    st.markdown("---")

# --- ESQUEMA VISUAL GENERAL ---
if os.path.exists("esquema_tolva.png"):
    st.subheader("🗺️ Esquema Guía General de Zonas")
    mostrar_imagen_responsive("esquema_tolva.png", caption="Plano de Ubicación General de Componentes - Tolva CAT 794 AC")
elif os.path.exists("esquema_tolva.jpg"):
    st.subheader("🗺️ Esquema Guía General de Zonas")
    mostrar_imagen_responsive("esquema_tolva.jpg", caption="Plano de Ubicación General de Componentes - Tolva CAT 794 AC")

# --- CONFIGURACIÓN DE ESTRUCTURA DE ZONAS ---
ESTRUCTURA_ZONAS = [
    {
        "titulo": "ZONA 01: CONJUNTO DE BLINDAJE DE TOLVA",
        "esquema": ["CONJUNTO DE BLINDAJE DE TOLVA.png"],
        "items": [
            ("1.1", "REFUERZO DE PISO #1", "VT/UT"),
            ("1.2", "REFUERZO DE PISO #2", "VT/UT"),
            ("1.3", "REFUERZO DE PISO #3", "VT/UT"),
            ("1.4", "ROCKBOX", "VT"),
            ("1.5", "REFUERZO FRONTAL #1", "VT/UT"),
            ("1.6", "REFUERZO FRONTAL #2", "VT/UT"),
            ("1.7", "REFUERZO FRONTAL #3", "VT/UT"),
            ("1.8", "REFUERZO LATERAL RH", "VT/UT"),
            ("1.9", "REFUERZO LATERAL LH", "VT"),
            ("1.10", "CORTAFLUJOS", "VT/UT")
        ]
    },
    {
        "titulo": "ZONA 02: CONJUNTO LATERAL (RH / LH)",
        "esquema": ["CONJUNTO LATERAL.png"],
        "items": [
            ("2.1", "PLANCHA LATERAL RH", "VT"),
            ("2.2", "VIGA CAJON LATERAL RH", "VT"),
            ("2.3", "PLANCHA LATERAL LH", "VT"),
            ("2.4", "VIGA CAJON LATERAL LH", "VT")
        ]
    },
    {
        "titulo": "ZONA 03: CANOPY",
        "esquema": ["CANOPY.png"],
        "items": [
            ("3.1", "PLANCHA RH", "VT"),
            ("3.2", "PLANCHA LH", "VT"),
            ("3.3", "DEFLECTOR RH", "VT"),
            ("3.4", "DEFLECTOR LH", "VT"),
            ("3.5", "PLANCHA FRONTAL CANOPY", "VT"),
            ("3.6", "CARTELAS DE PLANCHA FRONTAL", "VT"),
            ("3.7", "VIGA LATERAL RH", "VT"),
            ("3.8", "VIGA LATERAL LH", "VT"),
            ("3.9", "REFUERZO RH DE CANOPY", "VT"),
            ("3.10", "REFUERZO LH DE CANOPY", "VT")
        ]
    },
    {
        "titulo": "ZONA 04 Y 05: PLANCHAS DE PISO / PLANCHAS FRONTALES",
        "esquema": ["PLANCHAS FRONTALES.png", "PLANCHAS DE PISO.png"],
        "items": [
            ("4.1", "PLANCHA FRONTAL SUPERIOR", "VT"),
            ("4.2", "PLANCHA FRONTAL RH", "VT"),
            ("4.3", "PLANCHA FRONTAL LH", "VT"),
            ("5.1", "PLANCHA DE PISO RH", "VT/UT"),
            ("5.2", "PLANCHA DE PISO LH", "VT/UT"),
            ("5.3", "PLANCHA COLA DE PISO", "VT/UT")
        ]
    },
    {
        "titulo": "ZONA 06 Y 07: LONGUERINA DELANTERA, POSTERIOR Y VIGAS / GUIADORES",
        "esquema": ["LONGUERINA DELANTERA, POSTERIOR Y VIGAS.png", "GUIADORES.png"],
        "items": [
            ("6.1", "LONGUERINA DELANTERA RH", "VT"),
            ("6.2", "LONGUERINA DELANTERA LH", "VT"),
            ("6.3", "LONGUERINA POSTERIOR RH", "VT"),
            ("6.4", "LONGUERINA POSTERIOR LH", "VT"),
            ("6.5", "VIGA DE PISO #1 RH", "VT"),
            ("6.6", "VIGA CAJON DE PISO #1 LH", "VT"),
            ("6.7", "VIGA CAJON DE PISO #2 RH", "VT"),
            ("6.8", "VIGA CAJON DE PISO #2 LH", "VT"),
            ("6.9", "VIGA CAJON DE COLA", "VT"),
            ("7.1", "GUIADOR RH", "VT"),
            ("7.2", "GUIADOR LH", "VT")
        ]
    },
    {
        "titulo": "ZONA 08: CAJAS PIVOTE",
        "esquema": ["CAJAS PIVOTE.png"],
        "items": [
            ("8.1", "CAJA PIVOTE RH", "VT"),
            ("8.2", "CAJA PIVOTE LH", "VT"),
            ("8.3", "BUSHING DE CAJA PIVOTE RH", "VT"),
            ("8.4", "BUSHING DE CAJA PIVOTE LH", "VT"),
            ("8.5", "SEPARADOR DE CAJA PIVOTE", "VT")
        ]
    }
]

def mostrar_esquema_zona(nombres_archivo, titulo_zona):
    # Acepta un solo nombre (str) o una lista de nombres de archivo.
    # El esquema se muestra SIEMPRE VISIBLE al inicio de la zona (sin expander
    # colapsado) para que un técnico nuevo pueda guiarse de inmediato.
    if isinstance(nombres_archivo, str):
        nombres_archivo = [nombres_archivo]

    rutas_existentes = [
        os.path.join("imagenes_esquemas", n) for n in nombres_archivo
        if os.path.exists(os.path.join("imagenes_esquemas", n))
    ]

    if rutas_existentes:
        st.markdown("**🗺️ Esquema de referencia de la zona:**")
        if len(rutas_existentes) == 1:
            mostrar_imagen_responsive(rutas_existentes[0])
        else:
            cols = st.columns(len(rutas_existentes))
            for c, ruta in zip(cols, rutas_existentes):
                with c:
                    mostrar_imagen_responsive(ruta)
        st.markdown("")

# --- GESTOR FOTOGRÁFICO: COMPONENTE PROPIO (SIN LIBRERÍAS EXTERNAS) ---
def gestor_fotografico(label_foto, key_foto):
    st.markdown(f"**{label_foto}**")

    llave_img = f"img_{key_foto}"
    llave_anotada = f"{llave_img}_anotada"

    # Control para retomar foto
    if f"retomar_{key_foto}" in st.session_state and st.session_state[f"retomar_{key_foto}"]:
        for k in [llave_img, llave_anotada]:
            if k in st.session_state:
                del st.session_state[k]
        del st.session_state[f"retomar_{key_foto}"]

    # 1. CARGA DE LA IMAGEN
    if llave_img not in st.session_state:
        metodo = st.radio(
            f"Modo de Carga ({key_foto}):", 
            ["Galería / Archivo", "Cámara Directa"], 
            key=f"rad_{key_foto}", 
            horizontal=True
        )
        
        img_upload = None
        if metodo == "Cámara Directa":
            foto_b64 = camara_nativa(key=f"camnat_{key_foto}")
            if foto_b64:
                # foto_b64 viene como "data:image/jpeg;base64,XXXX"
                datos_binarios = base64.b64decode(foto_b64.split(",", 1)[1])
                img_upload = Image.open(io.BytesIO(datos_binarios))
        else:
            up_data = st.file_uploader(f"Subir {label_foto}", type=["jpg", "png", "jpeg"], key=f"up_{key_foto}")
            if up_data:
                img_upload = Image.open(up_data)

        if img_upload is not None:
            # 1) Corrige la rotación automática que guardan los celulares en
            #    los metadatos EXIF (si no se hace esto, algunas fotos de
            #    celular aparecen giradas o "aplastadas" al mostrarlas).
            # 2) Redimensiona conservando la PROPORCIÓN ORIGINAL de la foto
            #    (antes se forzaba siempre a 600x350, lo que distorsionaba
            #    fotos verticales tomadas con el celular).
            img_fija = ImageOps.exif_transpose(img_upload.convert("RGB"))
            img_resized = redimensionar_conservando_calidad(img_fija, max_lado=1400)
            st.session_state[llave_img] = img_resized
            st.rerun()

    # 2. ANOTACIÓN: la imagen se incrusta directo en el HTML (base64), por eso
    # no depende de una carga de recurso aparte y funciona igual en Streamlit
    # Cloud que en local. Además soporta dibujo con el dedo en celular.
    if llave_img in st.session_state:
        img_actual = st.session_state[llave_img]

        if st.button(f"🗑️ Retomar Foto", key=f"btn_retomar_{key_foto}"):
            st.session_state[f"retomar_{key_foto}"] = True
            st.rerun()

        buf = io.BytesIO()
        img_actual.save(buf, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        resultado = anotador_fotos(img_b64, key=f"anot_{key_foto}")
        if resultado:
            st.session_state[llave_anotada] = resultado

        if llave_anotada in st.session_state:
            st.caption("✅ Anotación guardada para esta foto.")

# --- PROCESAMIENTO Y DESPLIEGUE DE ZONAS ---
todos_los_rechazos = [] 

for idx_z, bloque_zona in enumerate(ESTRUCTURA_ZONAS):
    st.header(bloque_zona["titulo"])
    mostrar_esquema_zona(bloque_zona["esquema"], bloque_zona["titulo"])

    h1, h2, h3, h4, h5, h6, h7, h8, h9 = st.columns([0.6, 2.2, 1.2, 0.8, 1.0, 1.0, 1.0, 1.2, 1.2])
    with h1: st.markdown("**ZONA**")
    with h2: st.markdown("**DESCRIPCIÓN**")
    with h3: st.markdown("**FECHA**")
    with h4: st.markdown("**DEFECTO**")
    with h5: st.markdown("**LONG. (mm)**")
    with h6: st.markdown("**EST. POST.**")
    with h7: st.markdown("**TÉCNICA**")
    with h8: st.markdown("**CONDICIÓN**")
    with h9: st.markdown("**COMENTARIOS**")

    rechazos_de_esta_zona = []

    for idx_i, item in enumerate(bloque_zona["items"]):
        cod_z, desc_z, tec_def = item
        key_id = f"z{idx_z}_{idx_i}"

        c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([0.6, 2.2, 1.2, 0.8, 1.0, 1.0, 1.0, 1.2, 1.2])

        with c1: st.write(f"**{cod_z}**")
        with c2: st.write(desc_z)
        with c3: st.write(fecha_insp.strftime("%d/%m/%Y"))

        with c4:
            defecto = st.selectbox("", ["LF", "D", "DE", "DP", "F", "FA"], key=f"def_{key_id}", label_visibility="collapsed")

        es_lf = (defecto == "LF")

        with c5:
            if es_lf:
                longitud = "-"
                st.text_input("", value="-", disabled=True, key=f"long_{key_id}", label_visibility="collapsed")
            else:
                opc_long = st.selectbox("", ["Manual", "VARIOS"], key=f"opclong_{key_id}", label_visibility="collapsed")
                if opc_long == "VARIOS":
                    longitud = "VARIOS"
                else:
                    longitud = st.text_input("", value="100", key=f"longval_{key_id}", label_visibility="collapsed")

        with c6:
            if es_lf:
                est_post = "-"
                st.selectbox("", ["-"], disabled=True, key=f"est_{key_id}", label_visibility="collapsed")
            else:
                est_post = st.selectbox("", ["NR", "R"], key=f"est_{key_id}", label_visibility="collapsed")

        with c7:
            tecnica = st.selectbox("", ["VT", "VT/PT", "VT/UT"], index=2 if tec_def=="VT/UT" else 0, key=f"tec_{key_id}", label_visibility="collapsed")

        with c8:
            if es_lf:
                condicion = "ACEPTABLE"
                st.markdown("<span style='color:#48BB78; font-weight:bold;'>ACEPTABLE</span>", unsafe_allow_html=True)
            else:
                condicion = "RECHAZADO"
                st.markdown("<span style='color:#F56565; font-weight:bold;'>RECHAZADO</span>", unsafe_allow_html=True)

        with c9:
            if es_lf:
                comentario = "-"
                st.text_input("", value="-", disabled=True, key=f"com_{key_id}", label_visibility="collapsed")
            else:
                comentario = st.selectbox("", ["CREAR OT", "OT CREADA"], key=f"com_{key_id}", label_visibility="collapsed")

        if not es_lf:
            datos_defectuosos = {
                "zona": cod_z,
                "descripcion": desc_z,
                "defecto": defecto,
                "longitud": longitud,
                "est_post": est_post,
                "tecnica": tecnica,
                "comentario": comentario,
                "key_id": key_id
            }
            rechazos_de_esta_zona.append(datos_defectuosos)
            todos_los_rechazos.append(datos_defectuosos)

    if len(rechazos_de_esta_zona) > 0:
        st.subheader(f"📸 Registro Fotográfico de Defectos - {bloque_zona['titulo']}")
        for rechazo in rechazos_de_esta_zona:
            expander_label = f"📷 Fotos de Hallazgo: {rechazo['descripcion']} ({rechazo['zona']}) - Defecto: [{rechazo['defecto']}]"
            with st.expander(expander_label, expanded=True):
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    gestor_fotografico("Foto Panorámica", f"pano_{rechazo['key_id']}")
                with f_col2:
                    gestor_fotografico("Foto de Detalle", f"det_{rechazo['key_id']}")

    if "ZONA 02" in bloque_zona["titulo"]:
        with st.expander("📷 Letreros Obligatorios Especiales: Laterales RH / LH", expanded=False):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                gestor_fotografico("Letrero Lateral RH", "esp_z2_rh")
            with f_col2:
                gestor_fotografico("Letrero Lateral LH", "esp_z2_lh")
                
    elif "ZONA 08" in bloque_zona["titulo"]:
        with st.expander("📷 Letrero Obligatorio Especial: Posterior", expanded=False):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                gestor_fotografico("Letrero Posterior", "esp_z8_post")
            with f_col2:
                st.info("Requerido para la zona posterior (Z08).")

    st.caption("**Leyenda Defectos:** D: Desprendimiento | DE: Desgaste | DP: Desprendimiento Parcial | F: Fisurado | LF: Libre de fisura (Aceptable)")
    st.caption("**Leyenda Técnica:** NR: No Reparado | R: Reparado | VT: Inspección Visual | LP: Líquidos Penetrantes | UT: Ultrasonido")
    st.markdown("---")

# --- SECCIÓN 4: ZONAS A REPARAR ---
st.header("4. Resumen de Órdenes de Trabajo (Zonas a Reparar)")

if len(todos_los_rechazos) == 0:
    st.success("✔ No se registraron defectos. No hay reparaciones pendientes requeridas.")
else:
    st.caption("Resumen sugerido de Órdenes de Trabajo según los defectos reportados:")
    for idx_ot, rechazo in enumerate(todos_los_rechazos):
        defecto = rechazo["defecto"]
        prefijo = "SOLD_CBO" if defecto == "DE" else "SOLD_REP"
        codigo_sugerido = f"BK00{str(idx_ot + 1).zfill(5)}"
        
        col_ot1, col_ot2 = st.columns([3, 2])
        with col_ot1:
            st.code(f"{prefijo} {rechazo['descripcion']} ({rechazo['zona']}) - {rechazo['defecto']}")
        with col_ot2:
            st.text_input(
                f"Código Backlog SAP ({rechazo['zona']}):", 
                value=codigo_sugerido, 
                key=f"bk_{rechazo['key_id']}"
            )

st.success("✔ Sistema sincronizado perfectamente con el formato de Tolvas CAT.")