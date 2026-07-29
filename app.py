import streamlit as st
import json
import os
import io
import base64
import pandas as pd
from datetime import date
from PIL import Image, ImageOps
import openpyxl
from openpyxl.drawing.image import Image as OpenPyXLImage
from openpyxl.styles import Font, Alignment, Border, Side

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="Sistema de Inspección de Tolvas CAT", layout="wide")
st.title("📋 Reporte de Inspección de Tolvas CAT 794 AC")

# --- COMPONENTE DE ANOTACIÓN DE FOTOS ---
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
canvas { border:1px solid #444; width:100%; height:auto; touch-action:pan-y; display:block; }
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
      if (parentElement._herramienta === "none") return;
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
        canvas.style.touchAction = (btn.dataset.tool === "none") ? "pan-y" : "none";
      });
    });
    parentElement.querySelector('#deshacer').addEventListener("click", () => { parentElement._formas.pop(); redibujar(); });
    parentElement.querySelector('#limpiar').addEventListener("click", () => { parentElement._formas = []; redibujar(); });
    parentElement.querySelector('#guardar').addEventListener("click", () => {
      setStateValue('imagen_anotada', canvas.toDataURL('image/png'));
      estadoEl.textContent = "✅ Anotación guardada en memoria.";
    });

    parentElement._redibujar = redibujar;
  }

  if (data && data.imagen_base64 && parentElement._ultimaImagen !== data.imagen_base64) {
    parentElement._ultimaImagen = data.imagen_base64;
    const canvasEl = parentElement.querySelector('#lienzo');
    const img = new Image();
    img.onload = () => {
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
    resultado = _componente_anotador(
        data={"imagen_base64": imagen_base64_sin_prefijo},
        key=key,
        on_imagen_anotada_change=lambda: None
    )
    return resultado.imagen_anotada if resultado else None

# --- COMPONENTE DE CÁMARA CON ZOOM NATIVO ---
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
    resultado = _componente_camara(key=key, on_foto_capturada_change=lambda: None)
    return resultado.foto_capturada if resultado else None


# --- FUNCIONES AUXILIARES DE IMAGEN Y EXCEL ---
def redimensionar_conservando_calidad(img, max_lado=1400):
    ancho, alto = img.size
    escala = min(max_lado / max(ancho, alto), 1.0)
    if escala >= 1.0: return img
    nuevo_ancho = max(1, int(ancho * escala))
    nuevo_alto = max(1, int(alto * escala))
    return img.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)

def mostrar_imagen_responsive(ruta_o_objeto, caption=None):
    try: st.image(ruta_o_objeto, caption=caption, width="stretch")
    except TypeError:
        try: st.image(ruta_o_objeto, caption=caption, use_container_width=True)
        except TypeError:
            try: st.image(ruta_o_objeto, caption=caption, use_column_width=True)
            except TypeError: st.image(ruta_o_objeto, caption=caption)

def safe_write(ws, row, col, value):
    """Escribe en una celda previniendo de forma estricta el error de celdas combinadas."""
    try:
        ws.cell(row=row, column=col, value=value)
    except AttributeError:
        # El error TypeError anterior ocurría por la forma en que evaluabamos in merged_range.
        # Lo solucionamos extrayendo los bounds (limites) exactos del rango combinado.
        for merged_range in ws.merged_cells.ranges:
            min_col, min_row, max_col, max_row = merged_range.bounds
            if min_row <= row <= max_row and min_col <= col <= max_col:
                try:
                    ws.cell(row=min_row, column=min_col, value=value)
                except:
                    pass
                return
    except Exception:
        pass

def obtener_img_state(llave):
    foto_anotada = st.session_state.get(f"{llave}_anotada")
    foto_original = st.session_state.get(llave)
    if foto_anotada:
        datos_bin = base64.b64decode(foto_anotada.split(",", 1)[1])
        return Image.open(io.BytesIO(datos_bin))
    elif foto_original is not None:
        return foto_original
    return None

def _insertar_filas_seguro(ws, fila_insercion, cantidad):
    merges_originales = list(ws.merged_cells.ranges)
    for mc in merges_originales:
        ws.unmerge_cells(str(mc))
    ws.insert_rows(fila_insercion, amount=cantidad)
    for mc in merges_originales:
        min_col, min_row, max_col, max_row = mc.bounds
        if min_row >= fila_insercion:
            min_row += cantidad
            max_row += cantidad
        elif max_row >= fila_insercion:
            max_row += cantidad
        ws.merge_cells(start_row=min_row, start_column=min_col, end_row=max_row, end_column=max_col)

# --- GENERADOR DEL REPORTE EXCEL (LÓGICA DINÁMICA SEGURA) ---
def generar_reporte_excel(ruta_plantilla, cliente, lugar, fecha_insp, cod_equipo,
                           cod_tolva, horometro, cod_informe, revision, pm,
                           estructura_zonas, nombre_realizado, fecha_firma, firma_archivo,
                           todos_los_rechazos, matriz_espesores=None):
    
    wb = openpyxl.load_workbook(ruta_plantilla)
    ws = wb["TOLVA DT"]
    
    font_red = Font(color="FF0000", bold=True)
    font_black = Font(color="000000")
    title_font = Font(bold=True, size=11)
    title_alignment = Alignment(horizontal='center', vertical='center')
    desc_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    # 1. Datos Generales
    ws["C5"] = cliente
    ws["C6"] = lugar
    ws["C7"] = fecha_insp
    ws["H6"] = cod_equipo
    ws["H7"] = cod_tolva
    ws["L6"] = horometro
    ws["P5"] = cod_informe
    ws["P6"] = revision
    ws["P7"] = pm

    # 2. Matriz de Espesores (Búsqueda dinámica)
    if pm in ["1000H", "2000H"] and matriz_espesores is not None:
        fila_inicio_matriz = 15 
        for r in range(1, 100):
            val = ws.cell(row=r, column=3).value
            if val and isinstance(val, str) and ("ESPESORES" in val.upper() or "PUNTO 1" in val.upper()):
                fila_inicio_matriz = r + 2
                break
        
        for i in range(8):
            for j in range(7):
                safe_write(ws, fila_inicio_matriz + i, 3 + j, matriz_espesores.iloc[i, j])
                
        if (matriz_espesores == "-").all().all():
            safe_write(ws, fila_inicio_matriz - 1, 3, "NO SE REALIZÓ MEDICIÓN DE ESPESORES")

    # 3. Mapeo Dinámico de Zonas
    KEYWORDS_ZONAS = [
        "CONJUNTO DE BLINDAJE",
        "CONJUNTO LATERAL",
        "CANOPY",
        "PLANCHAS DE PISO",
        "LONGUERINA",
        "CAJAS PIVOTE"
    ]

    desplazamiento = 0
    for idx_z, bloque_zona in enumerate(estructura_zonas):
        # Encontrar fila del título de la zona actual en el Excel
        fila_header = None
        for r in range(1, 300):
            val = ws.cell(row=r, column=1).value
            if val and isinstance(val, str) and KEYWORDS_ZONAS[idx_z] in val.upper():
                fila_header = r
                break
                
        if fila_header is None:
            continue # Si por algo no halla la zona, la salta
            
        fila_inicio_items = fila_header + 2
        
        # Llenar la tabla de inspección (LF o Defectos)
        for idx_i, item in enumerate(bloque_zona["items"]):
            cod_z, desc_z, tec_def = item
            key_id = f"z{idx_z}_{idx_i}"
            fila = fila_inicio_items + idx_i
            
            defecto = st.session_state.get(f"def_{key_id}", "LF")
            es_lf = (defecto == "LF")
            
            safe_write(ws, fila, 5, fecha_insp.strftime("%d/%m/%Y") if isinstance(fecha_insp, date) else fecha_insp)
            safe_write(ws, fila, 7, defecto)
            safe_write(ws, fila, 8, st.session_state.get(f"longval_{key_id}", "-"))
            safe_write(ws, fila, 9, st.session_state.get(f"est_{key_id}", "-"))
            safe_write(ws, fila, 11, st.session_state.get(f"tec_{key_id}", tec_def))
            safe_write(ws, fila, 12, "ACEPTABLE" if es_lf else "RECHAZADO")
            safe_write(ws, fila, 14, st.session_state.get(f"com_{key_id}", "-"))
            
            # Color del texto de la condición
            for c_idx in [1, 2, 5, 7, 8, 9, 11, 12, 14]:
                try:
                    ws.cell(row=fila, column=c_idx).font = font_black if es_lf else font_red
                except: pass

        # Preparamos las fotos a insertar
        rechazos_zona = [r for r in todos_los_rechazos if r["key_id"].startswith(f"z{idx_z}_")]
        if idx_z == 1:
            rechazos_zona.append({"zona": "2", "descripcion": "LETRERO LATERAL RH", "defecto": "-", "key_id": "esp_z2_rh"})
            rechazos_zona.append({"zona": "2", "descripcion": "LETRERO LATERAL LH", "defecto": "-", "key_id": "esp_z2_lh"})
        elif idx_z == 5:
            rechazos_zona.append({"zona": "8", "descripcion": "LETRERO POSTERIOR", "defecto": "-", "key_id": "esp_z8_post"})

        fila_insercion_fotos = fila_inicio_items + len(bloque_zona["items"])
        
        # Insertar los bloques dinámicamente si hay defectos o zonas obligatorias
        for rechazo in rechazos_zona:
            # Insertar 2 filas en blanco empujando el resto del excel hacia abajo
            _insertar_filas_seguro(ws, fila_insercion_fotos, 2)
            
            # Ajustar alturas (25px para títulos, 300px para la foto)
            ws.row_dimensions[fila_insercion_fotos].height = 25
            ws.row_dimensions[fila_insercion_fotos+1].height = 300
            
            # Unir celdas dinámicamente
            ws.merge_cells(start_row=fila_insercion_fotos, start_column=1, end_row=fila_insercion_fotos, end_column=4)
            ws.merge_cells(start_row=fila_insercion_fotos, start_column=5, end_row=fila_insercion_fotos, end_column=11)
            ws.merge_cells(start_row=fila_insercion_fotos, start_column=12, end_row=fila_insercion_fotos, end_column=17)
            
            ws.merge_cells(start_row=fila_insercion_fotos+1, start_column=1, end_row=fila_insercion_fotos+1, end_column=4)
            ws.merge_cells(start_row=fila_insercion_fotos+1, start_column=5, end_row=fila_insercion_fotos+1, end_column=11)
            ws.merge_cells(start_row=fila_insercion_fotos+1, start_column=12, end_row=fila_insercion_fotos+1, end_column=17)
            
            # Pintar bordes
            for r_idx in [fila_insercion_fotos, fila_insercion_fotos+1]:
                for c_idx in range(1, 18):
                    try: ws.cell(row=r_idx, column=c_idx).border = thin_border
                    except: pass
            
            # Escribir Encabezados (con ortografía correcta)
            c_desc = ws.cell(row=fila_insercion_fotos, column=1)
            c_desc.value = "DESCRIPCIÓN"
            c_pano = ws.cell(row=fila_insercion_fotos, column=5)
            c_pano.value = "PANORÁMICO"
            c_det = ws.cell(row=fila_insercion_fotos, column=12)
            c_det.value = "DETALLE"
            
            for c in [c_desc, c_pano, c_det]:
                c.font = title_font
                c.alignment = title_alignment
            
            # Escribir cuadro de descripción del defecto
            desc_text = f"ZONA {rechazo['zona']}\n{rechazo['descripcion'].upper()}\n\n{rechazo['defecto']}"
            c_texto = ws.cell(row=fila_insercion_fotos+1, column=1)
            c_texto.value = desc_text
            c_texto.alignment = desc_alignment
            
            # Inyectar las fotos
            img_pano = obtener_img_state(f"img_pano_{rechazo['key_id']}")
            if img_pano:
                buf_pano = io.BytesIO()
                img_pano.thumbnail((420, 380), Image.LANCZOS)
                img_pano.save(buf_pano, format="PNG")
                buf_pano.seek(0)
                img_xl = OpenPyXLImage(buf_pano)
                img_xl.anchor = f"E{fila_insercion_fotos+1}"
                ws.add_image(img_xl)
                
            img_det = obtener_img_state(f"img_det_{rechazo['key_id']}")
            if img_det:
                buf_det = io.BytesIO()
                img_det.thumbnail((420, 380), Image.LANCZOS)
                img_det.save(buf_det, format="PNG")
                buf_det.seek(0)
                img_xl2 = OpenPyXLImage(buf_det)
                img_xl2.anchor = f"L{fila_insercion_fotos+1}"
                ws.add_image(img_xl2)
            else:
                if rechazo['key_id'].startswith("esp_"):
                    c_guion = ws.cell(row=fila_insercion_fotos+1, column=12)
                    c_guion.value = "-"
                    c_guion.alignment = title_alignment
                    
            fila_insercion_fotos += 2

    # 4. Zonas a Reparar (OTs) y Firmas (Búsqueda dinámica)
    fila_ot = None
    for r in range(1, 1000):
        val = ws.cell(row=r, column=1).value
        if val and isinstance(val, str) and "ZONAS A REPARAR" in val.upper():
            fila_ot = r + 2
            break
            
    if fila_ot:
        for idx_ot, rechazo in enumerate(todos_los_rechazos):
            if idx_ot >= 8: break # Límite de la plantilla
            defecto = rechazo["defecto"]
            prefijo = "SOLD_CBO" if defecto == "DE" else "SOLD_REP"
            codigo_sugerido = f"BK00{str(idx_ot + 1).zfill(5)}"
            codigo_backlog = st.session_state.get(f"bk_{rechazo['key_id']}", codigo_sugerido)
            texto_ot = f"{prefijo} {rechazo['descripcion']} ({rechazo['zona']}) - {codigo_backlog}"
            safe_write(ws, fila_ot, 1, texto_ot)
            fila_ot += 1

    fila_firma = None
    for r in range(1, 1000):
        val = ws.cell(row=r, column=1).value
        if val and isinstance(val, str) and "REALIZADO POR" in val.upper():
            fila_firma = r
            break

    if fila_firma:
        safe_write(ws, fila_firma + 2, 2, nombre_realizado)
        safe_write(ws, fila_firma + 4, 2, fecha_firma.strftime("%d/%m/%Y") if isinstance(fecha_firma, date) else fecha_firma)

        if firma_archivo is not None:
            firma_archivo.seek(0)
            img_firma = Image.open(firma_archivo).convert("RGB")
            img_firma.thumbnail((220, 90), Image.LANCZOS)
            buf_firma = io.BytesIO()
            img_firma.save(buf_firma, format="PNG")
            img_xl_firma = OpenPyXLImage(buf_firma)
            img_xl_firma.anchor = f"B{fila_firma+2}"
            ws.add_image(img_xl_firma)

    buf_final = io.BytesIO()
    wb.save(buf_final)
    buf_final.seek(0)
    return buf_final.getvalue(), []

def convertir_excel_a_pdf(bytes_excel):
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as carpeta_temp:
        ruta_xlsx = os.path.join(carpeta_temp, "reporte.xlsx")
        with open(ruta_xlsx, "wb") as f:
            f.write(bytes_excel)
        try:
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", carpeta_temp, ruta_xlsx], check=True, timeout=120, capture_output=True)
        except Exception:
            return None
        ruta_pdf = os.path.join(carpeta_temp, "reporte.pdf")
        if os.path.exists(ruta_pdf):
            with open(ruta_pdf, "rb") as f:
                return f.read()
        return None

# --- BASE DE DATOS LOCAL PARA RECORDAR TOLVA ---
DB_FILE = os.path.join("base_datos", "tolvas_db.json")

def cargar_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try: return json.load(f)
            except: return {}
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

# --- SECCIÓN MEDICIÓN DE ESPESORES ---
matriz_espesores_final = None

if pm in ["1000H", "2000H"]:
    st.header("📏 Mapeo / Medición de Espesores (Matriz 8x7)")
    no_medicion = st.checkbox("⚠️ Marcar como 'NO SE REALIZÓ MEDICIÓN DE ESPESORES'", key="check_no_medicion")

    if no_medicion:
        st.warning("Se ha seleccionado omitir la medición. El reporte se llenará con '-' y agregará la nota explicativa.")
        matriz_espesores_final = pd.DataFrame([["-"]*7 for _ in range(8)], 
                                    index=[f"Punto {i+1}" for i in range(8)],
                                    columns=[f"Eje {j+1}" for j in range(7)])
        st.dataframe(matriz_espesores_final, use_container_width=True)
    else:
        st.caption("Ingrese manualmente las lecturas de ultrasonido (mm) en la matriz:")
        df_init_espesores = pd.DataFrame([[20.00]*7 for _ in range(8)], 
                               index=[f"Punto {i+1}" for i in range(8)],
                               columns=[f"Eje {j+1}" for j in range(7)])
        
        column_config_espesores = {
            f"Eje {i+1}": st.column_config.NumberColumn(width=65, format="%.2f") for i in range(7)
        }

        matriz_espesores_final = st.data_editor(
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
            ("1.1", "REFUERZO DE PISO #1", "VT/UT"), ("1.2", "REFUERZO DE PISO #2", "VT/UT"),
            ("1.3", "REFUERZO DE PISO #3", "VT/UT"), ("1.4", "ROCKBOX", "VT"),
            ("1.5", "REFUERZO FRONTAL #1", "VT/UT"), ("1.6", "REFUERZO FRONTAL #2", "VT/UT"),
            ("1.7", "REFUERZO FRONTAL #3", "VT/UT"), ("1.8", "REFUERZO LATERAL RH", "VT/UT"),
            ("1.9", "REFUERZO LATERAL LH", "VT"), ("1.10", "CORTAFLUJOS", "VT/UT")
        ]
    },
    {
        "titulo": "ZONA 02: CONJUNTO LATERAL (RH / LH)",
        "esquema": ["CONJUNTO LATERAL.png"],
        "items": [
            ("2.1", "PLANCHA LATERAL RH", "VT"), ("2.2", "VIGA CAJON LATERAL RH", "VT"),
            ("2.3", "PLANCHA LATERAL LH", "VT"), ("2.4", "VIGA CAJON LATERAL LH", "VT")
        ]
    },
    {
        "titulo": "ZONA 03: CANOPY",
        "esquema": ["CANOPY.png"],
        "items": [
            ("3.1", "PLANCHA RH", "VT"), ("3.2", "PLANCHA LH", "VT"),
            ("3.3", "DEFLECTOR RH", "VT"), ("3.4", "DEFLECTOR LH", "VT"),
            ("3.5", "PLANCHA FRONTAL CANOPY", "VT"), ("3.6", "CARTELAS DE PLANCHA FRONTAL", "VT"),
            ("3.7", "VIGA LATERAL RH", "VT"), ("3.8", "VIGA LATERAL LH", "VT"),
            ("3.9", "REFUERZO RH DE CANOPY", "VT"), ("3.10", "REFUERZO LH DE CANOPY", "VT")
        ]
    },
    {
        "titulo": "ZONA 04 Y 05: PLANCHAS DE PISO / PLANCHAS FRONTALES",
        "esquema": ["PLANCHAS FRONTALES.png", "PLANCHAS DE PISO.png"],
        "items": [
            ("4.1", "PLANCHA FRONTAL SUPERIOR", "VT"), ("4.2", "PLANCHA FRONTAL RH", "VT"),
            ("4.3", "PLANCHA FRONTAL LH", "VT"), ("5.1", "PLANCHA DE PISO RH", "VT/UT"),
            ("5.2", "PLANCHA DE PISO LH", "VT/UT"), ("5.3", "PLANCHA COLA DE PISO", "VT/UT")
        ]
    },
    {
        "titulo": "ZONA 06 Y 07: LONGUERINA DELANTERA, POSTERIOR Y VIGAS / GUIADORES",
        "esquema": ["LONGUERINA DELANTERA, POSTERIOR Y VIGAS.png", "GUIADORES.png"],
        "items": [
            ("6.1", "LONGUERINA DELANTERA RH", "VT"), ("6.2", "LONGUERINA DELANTERA LH", "VT"),
            ("6.3", "LONGUERINA POSTERIOR RH", "VT"), ("6.4", "LONGUERINA POSTERIOR LH", "VT"),
            ("6.5", "VIGA DE PISO #1 RH", "VT"), ("6.6", "VIGA CAJON DE PISO #1 LH", "VT"),
            ("6.7", "VIGA CAJON DE PISO #2 RH", "VT"), ("6.8", "VIGA CAJON DE PISO #2 LH", "VT"),
            ("6.9", "VIGA CAJON DE COLA", "VT"), ("7.1", "GUIADOR RH", "VT"), ("7.2", "GUIADOR LH", "VT")
        ]
    },
    {
        "titulo": "ZONA 08: CAJAS PIVOTE",
        "esquema": ["CAJAS PIVOTE.png"],
        "items": [
            ("8.1", "CAJA PIVOTE RH", "VT"), ("8.2", "CAJA PIVOTE LH", "VT"),
            ("8.3", "BUSHING DE CAJA PIVOTE RH", "VT"), ("8.4", "BUSHING DE CAJA PIVOTE LH", "VT"),
            ("8.5", "SEPARADOR DE CAJA PIVOTE", "VT")
        ]
    }
]

def mostrar_esquema_zona(nombres_archivo, titulo_zona):
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

# --- GESTOR FOTOGRÁFICO ---
def gestor_fotografico(label_foto, key_foto):
    st.markdown(f"**{label_foto}**")
    st.warning("⚠️ Recuerda hacer clic en '💾 Guardar anotación' en el lienzo si realizas trazos antes de generar el reporte.")

    llave_img = f"img_{key_foto}"
    llave_anotada = f"{llave_img}_anotada"

    if f"retomar_{key_foto}" in st.session_state and st.session_state[f"retomar_{key_foto}"]:
        for k in [llave_img, llave_anotada]:
            if k in st.session_state:
                del st.session_state[k]
        del st.session_state[f"retomar_{key_foto}"]

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
                datos_binarios = base64.b64decode(foto_b64.split(",", 1)[1])
                img_upload = Image.open(io.BytesIO(datos_binarios))
        else:
            up_data = st.file_uploader(f"Subir {label_foto}", type=["jpg", "png", "jpeg"], key=f"up_{key_foto}")
            if up_data:
                img_upload = Image.open(up_data)

        if img_upload is not None:
            img_fija = ImageOps.exif_transpose(img_upload.convert("RGB"))
            ancho, alto = img_fija.size
            escala = min(1400 / max(ancho, alto), 1.0)
            if escala < 1.0:
                img_fija = img_fija.resize((int(ancho * escala), int(alto * escala)), Image.LANCZOS)
            st.session_state[llave_img] = img_fija
            st.rerun()

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
            st.caption("✅ Anotación guardada en memoria.")

# --- PROCESAMIENTO Y DESPLIEGUE DE ZONAS ---
todos_los_rechazos = [] 

for idx_z, bloque_zona in enumerate(ESTRUCTURA_ZONAS):
    st.header(bloque_zona["titulo"])
    mostrar_esquema_zona(bloque_zona.get("esquema", []), bloque_zona["titulo"])

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

        with c1:
            st.caption("ZONA")
            st.write(f"**{cod_z}**")
        with c2:
            st.caption("DESCRIPCIÓN")
            st.write(desc_z)
        with c3:
            st.caption("FECHA")
            st.write(fecha_insp.strftime("%d/%m/%Y"))

        with c4:
            defecto = st.selectbox("DEFECTO", ["LF", "D", "DE", "DP", "F", "FA"], key=f"def_{key_id}")

        es_lf = (defecto == "LF")

        with c5:
            if es_lf:
                longitud = "-"
                st.text_input("LONG. (mm)", value="-", disabled=True, key=f"long_{key_id}")
            else:
                opc_long = st.selectbox("LONG. (mm)", ["Manual", "VARIOS"], key=f"opclong_{key_id}")
                if opc_long == "VARIOS":
                    longitud = "VARIOS"
                else:
                    longitud = st.text_input("Valor longitud", value="100", key=f"longval_{key_id}")

        with c6:
            if es_lf:
                est_post = "-"
                st.selectbox("EST. POST.", ["-"], disabled=True, key=f"est_{key_id}")
            else:
                est_post = st.selectbox("EST. POST.", ["NR", "R"], key=f"est_{key_id}")

        with c7:
            tecnica = st.selectbox("TÉCNICA", ["VT", "VT/PT", "VT/UT"], index=2 if tec_def=="VT/UT" else 0, key=f"tec_{key_id}")

        with c8:
            st.caption("CONDICIÓN")
            if es_lf:
                st.markdown("<span style='color:#48BB78; font-weight:bold;'>ACEPTABLE</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:#F56565; font-weight:bold;'>RECHAZADO</span>", unsafe_allow_html=True)

        with c9:
            if es_lf:
                comentario = "-"
                st.text_input("COMENTARIOS", value="-", disabled=True, key=f"com_{key_id}")
            else:
                comentario = st.selectbox("COMENTARIOS", ["CREAR OT", "OT CREADA"], key=f"com_{key_id}")

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
                gestor_fotografico("Letrero Lateral RH (Panorámico)", "pano_esp_z2_rh")
            with f_col2:
                gestor_fotografico("Letrero Lateral LH (Panorámico)", "pano_esp_z2_lh")
                
    elif "ZONA 08" in bloque_zona["titulo"]:
        with st.expander("📷 Letrero Obligatorio Especial: Posterior", expanded=False):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                gestor_fotografico("Letrero Posterior (Panorámico)", "pano_esp_z8_post")
            with f_col2:
                st.info("Requerido para la zona posterior (Z08). El campo 'Detalle' en el Excel se llenará automáticamente con '-'.")

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

st.markdown("---")
st.header("5. Firma del Responsable de la Inspección")

col_f1, col_f2 = st.columns(2)
with col_f1:
    nombre_realizado = st.text_input("Nombre de quien realiza la inspección:", key="firma_nombre")
    fecha_firma = st.date_input("Fecha de firma:", value=fecha_insp, key="firma_fecha")
with col_f2:
    firma_archivo = st.file_uploader("Subir imagen de firma (PNG/JPG):", type=["png", "jpg", "jpeg"], key="firma_upload")
    if firma_archivo:
        st.image(firma_archivo, caption="Vista previa de la firma", width=250)

st.markdown("---")
st.header("6. Generar Reporte Final")

RUTA_PLANTILLA = "plantilla_tolva.xlsx"
nombre_archivo_base = f"{cod_informe}_{fecha_insp.strftime('%Y%m%d')}"

if not os.path.exists(RUTA_PLANTILLA):
    st.error(
        f"⚠️ No se encontró el archivo '{RUTA_PLANTILLA}' en el proyecto. "
        "Sube la plantilla original de Excel a la misma carpeta que app.py en GitHub "
        "(con ese nombre exacto) para poder generar el reporte."
    )
else:
    if st.button("📥 Generar Reporte", type="primary"):
        with st.spinner("Generando el archivo Excel..."):
            excel_bytes, zonas_sin_espacio = generar_reporte_excel(
                ruta_plantilla=RUTA_PLANTILLA,
                cliente=cliente, lugar=lugar, fecha_insp=fecha_insp,
                cod_equipo=cod_equipo, cod_tolva=cod_tolva, horometro=horometro,
                cod_informe=cod_informe, revision=revision, pm=pm,
                estructura_zonas=ESTRUCTURA_ZONAS,
                nombre_realizado=nombre_realizado, fecha_firma=fecha_firma,
                firma_archivo=firma_archivo,
                todos_los_rechazos=todos_los_rechazos,
                matriz_espesores=matriz_espesores_final
            )
        st.session_state["_ultimo_excel_generado"] = excel_bytes
        st.success("✅ Reporte Excel generado correctamente.")

    if "_ultimo_excel_generado" in st.session_state:
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="💾 Descargar Excel",
                data=st.session_state["_ultimo_excel_generado"],
                file_name=f"{nombre_archivo_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col_dl2:
            if st.button("📄 Convertir y Descargar PDF"):
                with st.spinner("Convirtiendo a PDF... esto puede tardar un poco"):
                    pdf_bytes = convertir_excel_a_pdf(st.session_state["_ultimo_excel_generado"])
                if pdf_bytes:
                    st.download_button(
                        label="💾 Descargar PDF",
                        data=pdf_bytes,
                        file_name=f"{nombre_archivo_base}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.error(
                        "⚠️ No se pudo convertir a PDF. Esto pasa si el servidor no tiene "
                        "LibreOffice instalado (revisa que subiste el archivo 'packages.txt'). "
                        "Mientras tanto, puedes abrir el Excel descargado y usar "
                        "'Archivo > Exportar > Crear PDF/XPS' desde Excel o Google Sheets."
                    )
