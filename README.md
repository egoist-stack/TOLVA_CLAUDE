# Sistema de Inspección de Tolvas CAT 794 AC

## Publicar en GitHub y Streamlit Cloud

1. Crea un repositorio nuevo en GitHub (puede ser privado).
2. En tu PC, dentro de esta carpeta (app.py, requirements.txt, imagenes_esquemas/):

   git init
   git add .
   git commit -m "Primera version del sistema de inspeccion de tolvas"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
   git push -u origin main

3. Entra a https://share.streamlit.io con tu cuenta de GitHub.
4. "New app" -> selecciona el repositorio -> Main file path: app.py -> Deploy.
5. Te da una URL publica (https://tuapp.streamlit.app). Abrela en el celular
   y usa "Agregar a pantalla de inicio" para que se vea como app.

## Estructura de carpetas requerida

app.py
requirements.txt
imagenes_esquemas/
    CONJUNTO DE BLINDAJE DE TOLVA.png
    CONJUNTO LATERAL.png
    CANOPY.png
    PLANCHAS FRONTALES.png
    PLANCHAS DE PISO.png
    LONGUERINA DELANTERA, POSTERIOR Y VIGAS.png
    GUIADORES.png
    CAJAS PIVOTE.png

La carpeta base_datos/ se crea sola (guarda el ultimo codigo de tolva
usado por cada codigo de equipo). No subirla a GitHub si el repo es publico.
