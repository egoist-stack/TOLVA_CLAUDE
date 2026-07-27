import streamlit as st
import json
import os
import hashlib
import io
import pandas as pd
from datetime import date
from PIL import Image
from streamlit_drawable_canvas import st_canvas

# Configuración principal de la app
st.set_page_config(page_title="Sistema de Inspección de Tolvas CAT", layout="wide")

st.title("📋 Reporte de Inspección de Tolvas CAT 794 AC")

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
    st.image("esquema_tolva.png", caption="Plano de Ubicación General de Componentes - Tolva CAT 794 AC", use_column_width=True)
elif os.path.exists("esquema_tolva.jpg"):
    st.subheader("🗺️ Esquema Guía General de Zonas")
    st.image("esquema_tolva.jpg", caption="Plano de Ubicación General de Componentes - Tolva CAT 794 AC", use_column_width=True)

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
            st.image(rutas_existentes[0], use_column_width=True)
        else:
            cols = st.columns(len(rutas_existentes))
            for c, ruta in zip(cols, rutas_existentes):
                with c:
                    st.image(ruta, use_column_width=True)
        st.markdown("")

# --- GESTOR FOTOGRÁFICO: SOLUCIÓN NATIVA CON BACKGROUND_IMAGE ---
def gestor_fotografico(label_foto, key_foto):
    st.markdown(f"**{label_foto}**")

    llave_img = f"img_{key_foto}"

    # Control para retomar foto
    if f"retomar_{key_foto}" in st.session_state and st.session_state[f"retomar_{key_foto}"]:
        if llave_img in st.session_state: 
            del st.session_state[llave_img]
        if f"{llave_img}_hash" in st.session_state:
            del st.session_state[f"{llave_img}_hash"]
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
            cam_data = st.camera_input(f"Tomar {label_foto}", key=f"cam_{key_foto}")
            if cam_data:
                img_upload = Image.open(cam_data)
        else:
            up_data = st.file_uploader(f"Subir {label_foto}", type=["jpg", "png", "jpeg"], key=f"up_{key_foto}")
            if up_data:
                img_upload = Image.open(up_data)

        if img_upload is not None:
            # Redimensionamos a un tamaño fijo de referencia para que el canvas y la foto coincidan exactamente
            img_resized = img_upload.convert("RGB").resize((600, 350))

            # Calculamos un hash del contenido de la imagen. Este hash se usa
            # más abajo como parte de la "key" del canvas: es lo que obliga a
            # streamlit-drawable-canvas a RE-MONTAR el componente cuando la
            # foto cambia. Si la key no cambia, el componente asume que nada
            # cambió y puede no repintar el background_image (bug conocido
            # de la librería: no refresca el fondo si la key es estática).
            buf = io.BytesIO()
            img_resized.save(buf, format="PNG")
            img_hash = hashlib.md5(buf.getvalue()).hexdigest()[:10]

            st.session_state[llave_img] = img_resized
            st.session_state[f"{llave_img}_hash"] = img_hash
            st.rerun()

    # 2. RENDERIZADO NATIVO DIRECTO (SIN TRUCOS CSS)
    if llave_img in st.session_state:
        img_actual = st.session_state[llave_img]
        img_hash = st.session_state.get(f"{llave_img}_hash", "0")

        col_tool, col_btn = st.columns([3, 1])
        with col_tool:
            herramienta = st.selectbox(
                f"Herramienta ({label_foto}):", 
                ["circle", "rect", "line", "freedraw"], 
                format_func=lambda x: "⭕ Círculo / Elipse" if x=="circle" else ("🔲 Rectángulo" if x=="rect" else ("↗️ Flecha / Línea" if x=="line" else "✏️ Dibujo Libre")),
                key=f"tool_{key_foto}"
            )
        with col_btn:
            if st.button(f"🗑️ Retomar Foto", key=f"btn_retomar_{key_foto}"):
                st.session_state[f"retomar_{key_foto}"] = True
                st.rerun()

        # SOLUCIÓN AL BUG DE DESINCRONIZACIÓN:
        # La key incluye el hash de la imagen (no solo key_foto). Así, cada vez
        # que se sube/toma una foto NUEVA, la key cambia y streamlit-drawable-canvas
        # se re-monta desde cero con el fondo correcto. Mientras la foto no cambie
        # (p.ej. solo cambias la herramienta de dibujo), la key se mantiene igual
        # y el dibujo hecho por el usuario no se pierde.
        st_canvas(
            fill_color="rgba(255, 0, 0, 0.2)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_color="",
            background_image=img_actual,
            update_streamlit=True,
            height=350,
            width=600,
            drawing_mode=herramienta,
            key=f"canvas_{key_foto}_{img_hash}"
        )

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