import base64
from datetime import datetime
import io
import os
import shutil
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="Wuanaguanare Pro - Planta Madre",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Forzar idioma español en el DOM sin advertencias de deprecación
st.html("<script>window.parent.document.documentElement.lang = 'es';</script>")

# =====================================================================
# CONFIGURACIÓN VISUAL PRO: OCULTAR MARCA DE AGUA, DEPLOY Y ELEMENTOS FIJOS
# =====================================================================
st.markdown(
    """
    <style>
        header[data-testid="stHeader"] {
            display: none !important;
        }
        [data-testid="stSidebarCollapseButton"], 
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        section[data-testid="stSidebar"] {
            display: block !important;
            visibility: visible !important;
            width: 300px !important;
            min-width: 300px !important;
            max-width: 300px !important;
            border-right: none !important;
        }
        section[data-testid="stSidebar"] > div {
            width: 300px !important;
            border-right: none !important;
        }
        section[data-testid="stSidebar"] hr {
            display: none !important;
        }
        
        /* Ocultar completamente elementos de Streamlit Cloud (Deploy, Footer, Menú, Badges) */
        footer { visibility: hidden; display: none !important; }
        #MainMenu { visibility: hidden; display: none !important; }
        [data-testid="stStatusWidget"] { visibility: hidden; display: none !important; }
        .stDeployButton { display: none !important; visibility: hidden !important; opacity: 0 !important; pointer-events: none !important; }
        [data-testid="stToolbar"] { display: none !important; visibility: hidden !important; opacity: 0 !important; }
        [data-testid="stDecoration"] { display: none !important; }
        div[class*="viewerBadge"] { 
            display: none !important; 
            visibility: hidden !important; 
            opacity: 0 !important; 
            pointer-events: none !important; 
        }
        
        /* Ocultar el aviso de "Press Enter to apply" en todos los inputs */
        [data-testid="InputInstructions"] {
            display: none !important;
        }
        .block-container {
            padding-top: 2rem !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# =====================================================================
# 1. BASE DE DATOS INDUSTRIAL Y GESTIÓN DE USUARIOS
# =====================================================================


def get_connection():
  conn = sqlite3.connect("wuanaguanare_db.sqlite", check_same_thread=False)
  conn.execute("PRAGMA foreign_keys = ON;")
  conn.execute("PRAGMA journal_mode = WAL;")
  return conn


def init_db():
  try:
    conn = get_connection()
    c = conn.cursor()

    # Tabla de Usuarios y Credenciales del Sistema
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios_sistema (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  usuario TEXT UNIQUE, 
                  password TEXT, 
                  rol TEXT)""")

    # Crear usuario TIC por defecto si la tabla está totalmente vacía
    c.execute("SELECT COUNT(*) FROM usuarios_sistema")
    if c.fetchone()[0] == 0:
      c.execute(
          "INSERT INTO usuarios_sistema (usuario, password, rol) VALUES (?, ?,"
          " ?)",
          ("tic", "admin123", "TIC"),
      )
      c.execute(
          "INSERT INTO usuarios_sistema (usuario, password, rol) VALUES (?, ?,"
          " ?)",
          ("gerencia", "gerencia123", "Gerencia"),
      )
      c.execute(
          "INSERT INTO usuarios_sistema (usuario, password, rol) VALUES (?, ?,"
          " ?)",
          ("almacen", "almacen123", "Almacén"),
      )
      c.execute(
          "INSERT INTO usuarios_sistema (usuario, password, rol) VALUES (?, ?,"
          " ?)",
          ("seguimiento", "argon123", "Seguimiento"),
      )

    # Tablas operativas principales
    c.execute("""CREATE TABLE IF NOT EXISTS cilindros (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  nombre TEXT UNIQUE, 
                  presion_inicial INTEGER, 
                  presion_actual INTEGER)""")

    c.execute("""CREATE TABLE IF NOT EXISTS inventario (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  codigo TEXT UNIQUE, 
                  insumo TEXT, 
                  cantidad REAL, 
                  unidad TEXT,
                  stock_minimo REAL DEFAULT 0.0,
                  costo_unitario REAL DEFAULT 0.0)""")

    c.execute("""CREATE TABLE IF NOT EXISTS registros_diarios (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  fecha TEXT, 
                  cilindro TEXT, 
                  soldador TEXT, 
                  presion_inicio INTEGER, 
                  presion_cierre INTEGER, 
                  consumo_argon INTEGER, 
                  soldadura_lineal REAL DEFAULT 0.0, 
                  soldadura_no_lineal REAL DEFAULT 0.0, 
                  punteos INTEGER DEFAULT 0, 
                  tungstenos INTEGER DEFAULT 0, 
                  varilla_gastada REAL DEFAULT 0.0,
                  orden_trabajo TEXT DEFAULT 'GENERAL')""")

    c.execute("""CREATE TABLE IF NOT EXISTS operadores (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  nombre TEXT UNIQUE)""")

    c.execute("""CREATE TABLE IF NOT EXISTS historial_entregas (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  fecha TEXT, 
                  codigo_insumo TEXT, 
                  insumo TEXT, 
                  cantidad REAL, 
                  unidad TEXT, 
                  operador TEXT,
                  orden_trabajo TEXT DEFAULT 'GENERAL')""")

    # Migraciones de columnas seguras
    c.execute("PRAGMA table_info(cilindros)")
    cols_cil = [col[1] for col in c.fetchall()]
    if "presion_inicial" not in cols_cil:
      c.execute(
          "ALTER TABLE cilindros ADD COLUMN presion_inicial INTEGER DEFAULT 0"
      )
    if "presion_actual" not in cols_cil:
      c.execute(
          "ALTER TABLE cilindros ADD COLUMN presion_actual INTEGER DEFAULT 0"
      )

    c.execute("PRAGMA table_info(inventario)")
    cols_inv = [col[1] for col in c.fetchall()]
    if "stock_minimo" not in cols_inv:
      c.execute(
          "ALTER TABLE inventario ADD COLUMN stock_minimo REAL DEFAULT 0.0"
      )
    if "costo_unitario" not in cols_inv:
      c.execute(
          "ALTER TABLE inventario ADD COLUMN costo_unitario REAL DEFAULT 0.0"
      )

    c.execute("PRAGMA table_info(registros_diarios)")
    cols_reg = [col[1] for col in c.fetchall()]
    if "soldadura_lineal" not in cols_reg:
      c.execute(
          "ALTER TABLE registros_diarios ADD COLUMN soldadura_lineal REAL"
          " DEFAULT 0.0"
      )
    if "soldadura_no_lineal" not in cols_reg:
      c.execute(
          "ALTER TABLE registros_diarios ADD COLUMN soldadura_no_lineal REAL"
          " DEFAULT 0.0"
      )
    if "punteos" not in cols_reg:
      c.execute(
          "ALTER TABLE registros_diarios ADD COLUMN punteos INTEGER DEFAULT 0"
      )
    if "tungstenos" not in cols_reg:
      c.execute(
          "ALTER TABLE registros_diarios ADD COLUMN tungstenos INTEGER DEFAULT"
          " 0"
      )
    if "varilla_gastada" not in cols_reg:
      c.execute(
          "ALTER TABLE registros_diarios ADD COLUMN varilla_gastada REAL"
          " DEFAULT 0.0"
      )
    if "orden_trabajo" not in cols_reg:
      c.execute(
          "ALTER TABLE registros_diarios ADD COLUMN orden_trabajo TEXT DEFAULT"
          " 'GENERAL'"
      )

    c.execute("PRAGMA table_info(historial_entregas)")
    cols_hist = [col[1] for col in c.fetchall()]
    if "codigo_insumo" not in cols_hist:
      c.execute("ALTER TABLE historial_entregas ADD COLUMN codigo_insumo TEXT")
    if "orden_trabajo" not in cols_hist:
      c.execute(
          "ALTER TABLE historial_entregas ADD COLUMN orden_trabajo TEXT"
          " DEFAULT 'GENERAL'"
      )

    conn.commit()
    conn.close()
  except Exception as e:
    st.error(f"Error crítico al inicializar la base de datos: {e}")


init_db()

# =====================================================================
# SISTEMA DE AUTENTICACIÓN DINÁMICO DESDE BASE DE DATOS
# =====================================================================
if "autenticado" not in st.session_state:
  st.session_state.autenticado = False
  st.session_state.rol = None

if not st.session_state.autenticado:
  col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
  with col_l2:
    st.markdown("<br><br>", unsafe_allow_html=True)
    logo_path = None
    if os.path.exists("logo.png"):
      logo_path = "logo.png"
    elif os.path.exists("logo.jpg"):
      logo_path = "logo.jpg"
    elif os.path.exists("Logo.ico"):
      logo_path = "Logo.ico"

    if logo_path and not logo_path.endswith(".ico"):
      with open(logo_path, "rb") as f:
        img_bytes = f.read()
      encoded_img = base64.b64encode(img_bytes).decode()
      ext = logo_path.split(".")[-1]
      st.markdown(
          f"""
                <div style="display: flex; justify-content: center; margin-bottom: 1rem; pointer-events: none;">
                    <img src="data:image/{ext};base64,{encoded_img}" style="width: 150px; pointer-events: none; user-select: none;">
                </div>
                """,
          unsafe_allow_html=True,
      )

    st.markdown(
        "<h2 style='text-align: center;'>Wuanaguanare Pro</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: gray;'>Acceso Corporativo"
        " Seguro en la Nube</p>",
        unsafe_allow_html=True,
    )

    usuario_input = st.text_input("Usuario")
    password_input = st.text_input("Contraseña", type="password")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Iniciar Sesión", type="primary", use_container_width=True):
      conn = get_connection()
      c = conn.cursor()
      c.execute(
          "SELECT rol FROM usuarios_sistema WHERE usuario = ? AND password = ?",
          (usuario_input.strip().lower(), password_input.strip()),
      )
      resultado_user = c.fetchone()
      conn.close()

      if resultado_user:
        st.session_state.autenticado = True
        st.session_state.rol = resultado_user[0]
        st.rerun()
      else:
        st.error("Usuario o contraseña incorrectos.")

  st.stop()


# Función de cierre y purga transaccional
def cerrar_y_reiniciar_proyecto(directorio_respaldos="historico_db"):
  if not os.path.exists(directorio_respaldos):
    os.makedirs(directorio_respaldos)
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  ruta_respaldo = os.path.join(
      directorio_respaldos, f"respaldo_proyecto_{timestamp}.sqlite"
  )
  try:
    if os.path.exists("wuanaguanare_db.sqlite"):
      shutil.copy2("wuanaguanare_db.sqlite", ruta_respaldo)

    conn = get_connection()
    with conn:
      conn.execute("DELETE FROM registros_diarios;")
      conn.execute("DELETE FROM historial_entregas;")
      conn.execute(
          "DELETE FROM sqlite_sequence WHERE name IN"
          " ('registros_diarios', 'historial_entregas');"
      )
    conn.close()

    conn_vacuum = sqlite3.connect(
        "wuanaguanare_db.sqlite", check_same_thread=False
    )
    conn_vacuum.isolation_level = None
    conn_vacuum.execute("VACUUM;")
    conn_vacuum.close()

    return (
        True,
        f"Proyecto cerrado con éxito. Histórico guardado en '{ruta_respaldo}' y"
        " tablas transaccionales restablecidas a cero.",
    )
  except Exception as e:
    return False, f"Error crítico al intentar restablecer la base de datos: {e}"


# =====================================================================
# 2. MENÚ LATERAL Y CONTROL DE ROLES
# =====================================================================
logo_path = None
if os.path.exists("logo.png"):
  logo_path = "logo.png"
elif os.path.exists("logo.jpg"):
  logo_path = "logo.jpg"

if logo_path:
  with open(logo_path, "rb") as f:
    img_bytes = f.read()
  encoded_img = base64.b64encode(img_bytes).decode()
  ext = logo_path.split(".")[-1]
  st.sidebar.markdown(
      f"""
        <div style="display: flex; justify-content: center; margin-bottom: 0.2rem; pointer-events: none;">
            <img src="data:image/{ext};base64,{encoded_img}" style="width: 100%; max-width: 100%; pointer-events: none; user-select: none;">
        </div>
        """,
      unsafe_allow_html=True,
  )
else:
  st.sidebar.title("WUANAGUANARE PMW")

st.sidebar.caption("Software Industrial en la Nube v2.7 Pro")

rol_actual = st.session_state.get("rol", "TIC")

if rol_actual == "TIC":
  opciones_menu = [
      "REGISTRO DIARIO GAS ARGÓN",
      "GESTIÓN DE PLANTA Y PROYECTOS",
      "REPORTES Y ANALÍTICA PRO",
  ]
elif rol_actual == "Seguimiento":
  opciones_menu = [
      "REGISTRO DIARIO GAS ARGÓN",
      "REPORTES Y ANALÍTICA PRO",
  ]
elif rol_actual == "Almacén":
  opciones_menu = ["GESTIÓN DE PLANTA Y PROYECTOS"]
elif rol_actual == "Gerencia":
  opciones_menu = ["REPORTES Y ANALÍTICA PRO"]
else:
  opciones_menu = ["REGISTRO DIARIO GAS ARGÓN"]

menu = st.sidebar.radio("Navegación", opciones_menu)

st.sidebar.write("---")
st.sidebar.markdown(f"Conectado como: **{rol_actual}**")
if st.sidebar.button(
    "Cerrar Sesión", use_container_width=True, type="secondary"
):
  st.session_state.autenticado = False
  st.session_state.rol = None
  st.rerun()

st.sidebar.write("---")
st.sidebar.subheader("Seguridad de Datos")
if os.path.exists("wuanaguanare_db.sqlite"):
  with open("wuanaguanare_db.sqlite", "rb") as db_file:
    st.sidebar.download_button(
        label="Descargar Respaldo (Backup)",
        data=db_file,
        file_name=(
            "backup_wuanaguanare_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}.sqlite"
        ),
        mime="application/x-sqlite3",
        use_container_width=True,
    )

# Alerta global de stock bajo en barra lateral
conn = get_connection()
df_stock_check = pd.read_sql_query(
    "SELECT insumo, cantidad, stock_minimo, unidad FROM inventario WHERE"
    " stock_minimo > 0 AND cantidad <= stock_minimo",
    conn,
)
conn.close()

if not df_stock_check.empty:
  st.sidebar.error("¡Atención! Insumos en Stock Crítico:")
  for _, row in df_stock_check.iterrows():
    st.sidebar.markdown(
        f"- **{row['insumo']}**: {row['cantidad']} {row['unidad']} (Mín:"
        f" {row['stock_minimo']})"
    )

# =====================================================================
# MÓDULO 1: REGISTRO DIARIO
# =====================================================================
if menu == "REGISTRO DIARIO GAS ARGÓN":
  st.header("Registro Diario Gas Argón y Producción")

  conn = get_connection()
  cilindros_df = pd.read_sql_query(
      "SELECT nombre, presion_actual FROM cilindros", conn
  )
  operadores_df = pd.read_sql_query("SELECT nombre FROM operadores", conn)
  conn.close()

  dict_presiones = (
      dict(zip(cilindros_df["nombre"], cilindros_df["presion_actual"]))
      if not cilindros_df.empty
      else {}
  )
  lista_cilindros = list(dict_presiones.keys())
  lista_operadores = (
      operadores_df["nombre"].tolist() if not operadores_df.empty else []
  )

  options_cilindros = (
      ["-- Seleccione un cilindro --"] + lista_cilindros
      if lista_cilindros
      else ["Sin cilindros registrados"]
  )
  options_operadores = (
      ["-- Seleccione un operador --"] + lista_operadores
      if lista_operadores
      else ["Sin operadores registrados"]
  )

  cilindro_activo = st.selectbox(
      "Cilindro Activo", options=options_cilindros
  )

  if cilindro_activo and cilindro_activo not in [
      "-- Seleccione un cilindro --",
      "Sin cilindros registrados",
  ]:
    presion_actual_cil = dict_presiones.get(cilindro_activo, 0)
    st.info(
        f"Argón disponible en **{cilindro_activo}**:"
        f" **{presion_actual_cil} PSI**"
    )

  with st.form(key="form_registro_diario", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
      soldador = st.selectbox("Soldador / Operador", options=options_operadores)
      orden_trabajo = st.text_input(
          "Orden de Trabajo / Proyecto (Ej: OT-2026-04)", value="GENERAL"
      )
      p_cierre = st.number_input(
          "Presión Cierre (PSI)", min_value=0, value=0
      )
    with col2:
      soldadura_lineal = st.number_input(
          "Soldadura Lineal (m)", min_value=0.0, value=0.0, format="%.2f"
      )
      soldadura_no_lineal = st.number_input(
          "Soldadura No Lineal (m)", min_value=0.0, value=0.0, format="%.2f"
      )
      punteos = st.number_input("Punteos (Cantidad)", min_value=0, value=0)
      tungstenos = st.number_input("Tungstenos gastados", min_value=0, value=0)

    st.write("")
    submitted_jornada = st.form_submit_button(
        "Guardar Jornada", type="primary", use_container_width=True
    )

    if submitted_jornada:
      if not cilindro_activo or cilindro_activo in [
          "-- Seleccione un cilindro --",
          "Sin cilindros registrados",
      ]:
        st.error(
            "Debe seleccionar un cilindro válido en la lista desplegable."
        )
      elif not soldador or soldador in [
          "-- Seleccione un operador --",
          "Sin operadores registrados",
      ]:
        st.error(
            "Debe seleccionar un operador válido en la lista desplegable."
        )
      else:
        p_inicio_actual = int(dict_presiones.get(cilindro_activo, 0))
        if p_cierre > p_inicio_actual:
          st.error(
              f"La presión de cierre ({p_cierre} PSI) no puede ser mayor que"
              f" la presión inicial disponible ({p_inicio_actual} PSI)."
          )
        else:
          consumo_argon = p_inicio_actual - p_cierre
          consumo_varilla = soldadura_lineal * 23.0

          conn = get_connection()
          try:
            with conn:
              c = conn.cursor()
              c.execute(
                  """
                            INSERT INTO registros_diarios 
                            (fecha, cilindro, soldador, presion_inicio, presion_cierre, consumo_argon, soldadura_lineal, soldadura_no_lineal, punteos, tungstenos, varilla_gastada, orden_trabajo) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                  (
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      cilindro_activo,
                      soldador,
                      int(p_inicio_actual),
                      int(p_cierre),
                      int(consumo_argon),
                      float(soldadura_lineal),
                      float(soldadura_no_lineal),
                      int(punteos),
                      int(tungstenos),
                      float(consumo_varilla),
                      orden_trabajo.strip().upper(),
                  ),
              )
              c.execute(
                  "UPDATE cilindros SET presion_actual = ? WHERE nombre = ?",
                  (int(p_cierre), cilindro_activo),
              )
            st.session_state["toast_jornada"] = (
                f"Jornada guardada. OT: {orden_trabajo.upper()} | Consumo"
                f" argón: {consumo_argon} PSI"
            )
            st.rerun()
          except Exception as ex:
            st.error(f"Error crítico al guardar la jornada: {ex}")
          finally:
            conn.close()

  if "toast_jornada" in st.session_state:
    st.toast(st.session_state["toast_jornada"], icon="🚀")
    del st.session_state["toast_jornada"]

# =====================================================================
# MÓDULO 2: GESTIÓN DE PLANTA Y PROYECTOS
# =====================================================================
elif menu == "GESTIÓN DE PLANTA Y PROYECTOS":
  st.header("Gestión de Planta, Insumos y Accesos del Sistema")

  if rol_actual == "TIC":
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Cilindros",
        "Inventario e Insumos",
        "Operadores",
        "Gestión de Usuarios",
        "Cierre de Proyecto",
    ])
  else:
    tab1, tab2, tab3, tab5 = st.tabs([
        "Cilindros",
        "Inventario e Insumos",
        "Operadores",
        "Cierre de Proyecto",
    ])

  with tab1:
    st.subheader("Control de Cilindros de Argón")
    nombre_cilindro = st.text_input(
        "Nombre / Código del Cilindro", key="input_nom_cil"
    )
    presion_ini = st.number_input(
        "Presión Inicial (PSI)", min_value=0, value=0, key="input_presion_cil"
    )

    if st.button("Registrar Cilindro", key="btn_reg_cilindro"):
      if nombre_cilindro.strip() != "":
        try:
          conn = get_connection()
          with conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO cilindros (nombre, presion_inicial, presion_actual)"
                " VALUES (?, ?, ?)",
                (
                    nombre_cilindro.strip().upper(),
                    int(presion_ini),
                    int(presion_ini),
                ),
            )
          conn.close()
          st.toast(
              f"Cilindro {nombre_cilindro.strip().upper()} agregado"
              " correctamente.",
              icon="✅",
          )
          st.rerun()
        except sqlite3.IntegrityError:
          st.toast("Este cilindro ya se encuentra registrado.", icon="⚠️")
        except Exception as ex:
          st.toast(f"Error al registrar cilindro: {ex}", icon="❌")
      else:
        st.toast(
            "Debe ingresar un nombre o código de cilindro válido.", icon="⚠️"
        )

    st.write("---")
    st.subheader("Eliminar Cilindro")
    conn = get_connection()
    df_cil = pd.read_sql_query(
        "SELECT id, nombre, presion_inicial, presion_actual FROM cilindros",
        conn,
    )
    conn.close()

    lista_cils_del = df_cil["nombre"].tolist() if not df_cil.empty else []
    options_cil_del = ["-- Seleccione un cilindro --"] + lista_cils_del

    def click_eliminar_cilindro():
      cil_seleccionado = st.session_state.get("sel_cil_eliminar")
      if cil_seleccionado and cil_seleccionado != "-- Seleccione un cilindro --":
        try:
          conn = get_connection()
          with conn:
            c = conn.cursor()
            c.execute("DELETE FROM cilindros WHERE nombre = ?", (cil_seleccionado,))
          conn.close()
          st.toast(
              f"Cilindro {cil_seleccionado} eliminado exitosamente.", icon="✅"
          )
        except Exception as ex:
          st.toast(f"Error al eliminar: {ex}", icon="❌")
      else:
        st.toast("Seleccione un cilindro válido.", icon="⚠️")

    col_del_cil_sel, col_del_cil_btn = st.columns(
        [3, 1], vertical_alignment="bottom"
    )
    with col_del_cil_sel:
      st.selectbox(
          "Seleccionar Cilindro",
          options=options_cil_del,
          key="sel_cil_eliminar",
      )
    with col_del_cil_btn:
      st.button(
          "Eliminar",
          type="secondary",
          use_container_width=True,
          on_click=click_eliminar_cilindro,
          key="btn_del_cilindro",
      )

    st.write("")
    conn = get_connection()
    df_cil_actualizado = pd.read_sql_query("SELECT * FROM cilindros", conn)
    conn.close()
    st.dataframe(df_cil_actualizado, use_container_width=True, hide_index=True)

  with tab2:
    st.subheader("Gestión de Inventario e Insumos")
    unidad_seleccionada = st.selectbox(
        "Unidad de Medida Principal",
        options=["kg", "g", "Unidad", "Litros", "Metros", "Pares"],
        key="select_unidad_stock",
    )

    with st.form(key="form_inventario", clear_on_submit=True):
      col_inv1, col_inv2, col_inv3 = st.columns(3)
      with col_inv1:
        cod_ins = st.text_input("Código o Lote del Insumo")
        nombre_insumo = st.text_input("Nombre del Artículo")
      with col_inv2:
        if unidad_seleccionada in ["Unidad", "Pares"]:
          cant_ins = st.number_input(
              "Cantidad a Agregar", min_value=0, value=0, step=1, format="%d"
          )
          stock_min = st.number_input(
              "Stock Mínimo Alerta", min_value=0, value=0, step=1, format="%d"
          )
        else:
          cant_ins = st.number_input(
              "Cantidad a Agregar", min_value=0.0, value=0.0, format="%.2f"
          )
          stock_min = st.number_input(
              "Stock Mínimo Alerta", min_value=0.0, value=0.0, format="%.2f"
          )
      with col_inv3:
        costo_unit = st.number_input(
            "Costo Unitario ($)", min_value=0.0, value=0.0, format="%.2f"
        )
        st.write("")
        st.write("")
        submitted = st.form_submit_button(
            "Sumar / Guardar en Inventario",
            type="primary",
            use_container_width=True,
        )

      if submitted:
        if cod_ins.strip() == "":
          st.error("Debe ingresar un código o lote único.")
        elif nombre_insumo.strip() == "":
          st.error("Debe ingresar el nombre del artículo.")
        else:
          try:
            conn = get_connection()
            with conn:
              c = conn.cursor()
              c.execute(
                  """
                            INSERT INTO inventario (codigo, insumo, cantidad, unidad, stock_minimo, costo_unitario) 
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(codigo) DO UPDATE SET
                                insumo = excluded.insumo,
                                cantidad = inventario.cantidad + excluded.cantidad,
                                unidad = excluded.unidad,
                                stock_minimo = excluded.stock_minimo,
                                costo_unitario = excluded.costo_unitario
                        """,
                  (
                      cod_ins.strip().upper(),
                      nombre_insumo.strip().upper(),
                      float(cant_ins),
                      unidad_seleccionada,
                      float(stock_min),
                      float(costo_unit),
                  ),
              )
            conn.close()
            st.session_state["toast_msg"] = (
                f"Inventario actualizado: se agregaron {cant_ins}"
                f" {unidad_seleccionada} al insumo"
                f" '{nombre_insumo.strip().upper()}'."
            )
            st.rerun()
          except Exception as ex:
            st.error(f"Error: {ex}")

    if "toast_msg" in st.session_state:
      st.toast(st.session_state["toast_msg"], icon="✅")
      del st.session_state["toast_msg"]

    st.write("")
    st.subheader("Estado Actual del Inventario")
    conn = get_connection()
    df_inv = pd.read_sql_query(
        "SELECT codigo, insumo, cantidad, unidad, stock_minimo, costo_unitario"
        " FROM inventario",
        conn,
    )
    conn.close()
    if not df_inv.empty:
      st.dataframe(df_inv, use_container_width=True, hide_index=True)
    else:
      st.info("No hay insumos registrados en el inventario.")

    st.write("---")
    st.subheader("Registrar Entrega o Asignación de Insumo a Operador")
    conn = get_connection()
    df_inv_act = pd.read_sql_query(
        "SELECT codigo, insumo, cantidad, unidad FROM inventario", conn
    )
    df_ops_act = pd.read_sql_query("SELECT nombre FROM operadores", conn)
    conn.close()

    lista_codigos_inv = (
        df_inv_act["codigo"].tolist() if not df_inv_act.empty else []
    )
    options_entrega_inv = ["-- Seleccione un insumo --"] + lista_codigos_inv
    lista_nombres_ops = (
        df_ops_act["nombre"].tolist() if not df_ops_act.empty else []
    )
    options_entrega_ops = ["-- Seleccione un operador --"] + lista_nombres_ops

    insumo_elegido = st.selectbox(
        "Insumo del Inventario",
        options=options_entrega_inv,
        key="select_insumo_entrega",
    )
    stock_actual = 0.0
    unidad_art_base = "kg"
    if insumo_elegido != "-- Seleccione un insumo --":
      conn = get_connection()
      c = conn.cursor()
      c.execute(
          "SELECT insumo, cantidad, unidad FROM inventario WHERE codigo = ?",
          (insumo_elegido,),
      )
      res_u = c.fetchone()
      conn.close()
      if res_u:
        nombre_art_base, stock_actual, unidad_art_base = res_u

    if unidad_art_base == "kg":
      unidades_posibles_retiro = ["g", "kg"]
    elif unidad_art_base == "g":
      unidades_posibles_retiro = ["g", "kg"]
    elif unidad_art_base in ["Metros", "m"]:
      unidades_posibles_retiro = ["cm", "Metros"]
    elif unidad_art_base in ["Litros", "l"]:
      unidades_posibles_retiro = ["ml", "Litros"]
    else:
      unidades_posibles_retiro = [unidad_art_base]

    col_ent1, col_ent2, col_ent3, col_ent4 = st.columns(4)
    with col_ent1:
      operador_elegido = st.selectbox(
          "Operador Asignado", options=options_entrega_ops, key="ent_op"
      )
    with col_ent2:
      ot_entrega = st.text_input(
          "Orden de Trabajo / OT", value="GENERAL", key="ent_ot"
      )
    with col_ent3:
      unidad_retiro = st.selectbox(
          "Unidad de Retiro", options=unidades_posibles_retiro, key="ent_unidad"
      )
    with col_ent4:
      if unidad_retiro in ["Unidad", "Pares"]:
        cant_entrega = st.number_input(
            "Cantidad",
            min_value=0,
            value=0,
            step=1,
            format="%d",
            key="ent_cant_int",
        )
      else:
        cant_entrega = st.number_input(
            "Cantidad",
            min_value=0.0,
            value=0.0,
            format="%.2f",
            key="ent_cant_float",
        )

    cant_a_descontar = float(cant_entrega)
    if unidad_art_base == "kg" and unidad_retiro == "g":
      cant_a_descontar = float(cant_entrega) / 1000.0
    elif unidad_art_base == "g" and unidad_retiro == "kg":
      cant_a_descontar = float(cant_entrega) * 1000.0
    elif unidad_art_base in ["Metros", "m"] and unidad_retiro == "cm":
      cant_a_descontar = float(cant_entrega) / 100.0
    elif unidad_art_base in ["Litros", "l"] and unidad_retiro == "ml":
      cant_a_descontar = float(cant_entrega) / 1000.0

    if insumo_elegido != "-- Seleccione un insumo --":
      st.info(
          "Stock disponible en almacén: **"
          f"{stock_actual} {unidad_art_base}**"
      )
      if cant_a_descontar > stock_actual:
        st.warning(
            "**¡Alerta de Stock Insuficiente!** Estás solicitando"
            f" {cant_entrega} {unidad_retiro}, pero solo tienes"
            f" **{stock_actual} {unidad_art_base}** disponible."
        )

    if st.button(
        "Registrar Entrega",
        type="primary",
        use_container_width=True,
        key="btn_reg_entrega_direct",
    ):
      if insumo_elegido == "-- Seleccione un insumo --":
        st.error("Debe seleccionar un insumo válido.")
      elif operador_elegido == "-- Seleccione un operador --":
        st.error("Debe seleccionar un operador válido.")
      elif cant_entrega <= 0:
        st.error("La cantidad debe ser mayor a cero.")
      elif cant_a_descontar > stock_actual:
        st.error(
            f"Stock insuficiente. Solo tienes {stock_actual}"
            f" {unidad_art_base} disponible."
        )
      else:
        try:
          conn = get_connection()
          with conn:
            c = conn.cursor()
            nuevo_stock = stock_actual - cant_a_descontar
            c.execute(
                "UPDATE inventario SET cantidad = ? WHERE codigo = ?",
                (nuevo_stock, insumo_elegido),
            )
            c.execute(
                """
                            INSERT INTO historial_entregas (fecha, codigo_insumo, insumo, cantidad, unidad, operador, orden_trabajo)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    insumo_elegido,
                    nombre_art_base,
                    float(cant_entrega),
                    unidad_retiro,
                    operador_elegido,
                    ot_entrega.strip().upper(),
                ),
            )
          conn.close()
          st.toast(
              f"Entrega de {cant_entrega} {unidad_retiro} de"
              f" '{nombre_art_base}' a {operador_elegido} registrada.",
              icon="🚀",
          )
          st.rerun()
        except Exception as ex:
          st.error(f"Error al registrar entrega: {ex}")

    st.write("")
    st.subheader("Historial de Entregas y Retiros")
    conn = get_connection()
    df_historial = pd.read_sql_query(
        "SELECT fecha, orden_trabajo, codigo_insumo, insumo, cantidad, unidad,"
        " operador FROM historial_entregas ORDER BY id DESC",
        conn,
    )
    conn.close()
    if not df_historial.empty:
      st.dataframe(df_historial, use_container_width=True, hide_index=True)
    else:
      st.info("No hay entregas registradas todavía.")

    st.write("---")
    st.subheader("Eliminar Insumo del Inventario")
    options_inv_del = ["-- Seleccione un código de insumo --"] + lista_codigos_inv

    def click_eliminar_insumo_inv():
      inv_sel = st.session_state.get("sel_inv_eliminar")
      if inv_sel and inv_sel != "-- Seleccione un código de insumo --":
        try:
          conn = get_connection()
          with conn:
            c = conn.cursor()
            c.execute("DELETE FROM inventario WHERE codigo = ?", (inv_sel,))
          conn.close()
          st.toast(
              f"Insumo con código '{inv_sel}' eliminado exitosamente.", icon="✅"
          )
        except Exception as ex:
          st.toast(f"Error al eliminar: {ex}", icon="❌")
      else:
        st.toast("Seleccione un código de insumo válido.", icon="⚠️")

    col_del_inv_sel, col_del_inv_btn = st.columns(
        [3, 1], vertical_alignment="bottom"
    )
    with col_del_inv_sel:
      st.selectbox(
          "Seleccionar Código de Insumo",
          options=options_inv_del,
          key="sel_inv_eliminar",
      )
    with col_del_inv_btn:
      st.button(
          "Eliminar",
          type="secondary",
          use_container_width=True,
          on_click=click_eliminar_insumo_inv,
          key="btn_del_inv_item",
      )

  with tab3:
    st.subheader("Gestión de Operadores / Soldadores")

    def click_registrar_operador():
      val = st.session_state.input_nom_op.strip()
      if val != "":
        try:
          conn = get_connection()
          with conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO operadores (nombre) VALUES (?)", (val.upper(),)
            )
          conn.close()
          st.toast(f"Operador {val.upper()} registrado exitosamente.", icon="✅")
          st.session_state.input_nom_op = ""
        except sqlite3.IntegrityError:
          st.toast("Este operador ya se encuentra registrado.", icon="⚠️")
        except Exception as ex:
          st.toast(f"Error: {ex}", icon="❌")
      else:
        st.toast("Debe ingresar un nombre válido.", icon="⚠️")

    col_input, col_btn = st.columns([3, 1], vertical_alignment="bottom")
    with col_input:
      st.text_input("Nombre del Operador", key="input_nom_op")
    with col_btn:
      st.button(
          "Registrar",
          type="primary",
          use_container_width=True,
          on_click=click_registrar_operador,
          key="btn_reg_operador",
      )

    st.write("---")
    st.subheader("Eliminar Operador")
    conn = get_connection()
    df_op = pd.read_sql_query("SELECT id, nombre FROM operadores", conn)
    conn.close()

    lista_ops_del = df_op["nombre"].tolist() if not df_op.empty else []
    options_del = ["-- Seleccione un operador --"] + lista_ops_del

    def click_eliminar_operador():
      op_seleccionado = st.session_state.get("sel_op_eliminar")
      if op_seleccionado and op_seleccionado != "-- Seleccione un operador --":
        try:
          conn = get_connection()
          with conn:
            c = conn.cursor()
            c.execute(
                "DELETE FROM operadores WHERE nombre = ?", (op_seleccionado,)
            )
          conn.close()
          st.toast(
              f"Operador {op_seleccionado} eliminado exitosamente.", icon="✅"
          )
        except Exception as ex:
          st.toast(f"Error al eliminar: {ex}", icon="❌")
      else:
        st.toast("Seleccione un operador válido.", icon="⚠️")

    col_del_sel, col_del_btn = st.columns(
        [3, 1], vertical_alignment="bottom"
    )
    with col_del_sel:
      st.selectbox(
          "Seleccionar Operador", options=options_del, key="sel_op_eliminar"
      )
    with col_del_btn:
      st.button(
          "Eliminar",
          type="secondary",
          use_container_width=True,
          on_click=click_eliminar_operador,
          key="btn_del_operador",
      )

    st.write("")
    conn = get_connection()
    df_op_actualizado = pd.read_sql_query(
        "SELECT id, nombre FROM operadores", conn
    )
    conn.close()
    st.dataframe(df_op_actualizado, use_container_width=True, hide_index=True)

  if rol_actual == "TIC":
    with tab4:
      st.subheader("Administración de Usuarios y Accesos del Sistema")
      st.markdown(
          "Crea nuevos usuarios, modifica sus contraseñas o actualiza sus"
          " perfiles de acceso (Roles) de forma dinámica."
      )

      with st.form(key="form_nuevo_usuario", clear_on_submit=True):
        c_u1, c_u2, c_u3 = st.columns(3)
        with c_u1:
          nuevo_usuario = st.text_input("Nombre de Usuario")
        with c_u2:
          nueva_clave = st.text_input("Contraseña", type="password")
        with c_u3:
          nuevo_rol = st.selectbox(
              "Rol Asignado", ["TIC", "Gerencia", "Almacén", "Seguimiento"]
          )

        btn_crear_user = st.form_submit_button(
            "Crear / Actualizar Usuario en el Sistema", type="primary"
        )

        if btn_crear_user:
          if nuevo_usuario.strip() and nueva_clave.strip():
            try:
              conn = get_connection()
              with conn:
                c = conn.cursor()
                c.execute(
                    """
                                    INSERT INTO usuarios_sistema (usuario, password, rol) 
                                    VALUES (?, ?, ?)
                                    ON CONFLICT(usuario) DO UPDATE SET
                                        password = excluded.password,
                                        rol = excluded.rol
                                """,
                    (
                        nuevo_usuario.strip().lower(),
                        nueva_clave.strip(),
                        nuevo_rol,
                    ),
                )
              conn.close()
              st.success(
                  f"Usuario '{nuevo_usuario.strip().lower()}' guardado con"
                  " éxito."
              )
              st.rerun()
            except Exception as e:
              st.error(f"Error al guardar usuario: {e}")
          else:
            st.error("Debe completar el usuario y la contraseña.")

      st.write("---")
      st.subheader("Usuarios Registrados Actualmente")
      conn = get_connection()
      df_users = pd.read_sql_query(
          "SELECT id, usuario, rol FROM usuarios_sistema", conn
      )
      conn.close()
      st.dataframe(df_users, use_container_width=True, hide_index=True)

      st.write("---")
      st.subheader("Eliminar Usuario del Sistema")
      conn = get_connection()
      df_users_del = pd.read_sql_query(
          "SELECT usuario FROM usuarios_sistema", conn
      )
      conn.close()
      lista_users_del = (
          df_users_del["usuario"].tolist() if not df_users_del.empty else []
      )
      options_user_del = ["-- Seleccione un usuario --"] + lista_users_del

      def click_eliminar_usuario_sis():
        usr_sel = st.session_state.get("sel_user_eliminar")
        if usr_sel and usr_sel != "-- Seleccione un usuario --":
          if usr_sel == "tic":
            st.toast(
                "No se puede eliminar al administrador principal 'tic'.",
                icon="⚠️",
            )
          else:
            try:
              conn = get_connection()
              with conn:
                c = conn.cursor()
                c.execute(
                    "DELETE FROM usuarios_sistema WHERE usuario = ?", (usr_sel,)
                )
              conn.close()
              st.toast(
                  f"Usuario '{usr_sel}' eliminado exitosamente del sistema.",
                  icon="✅",
              )
            except Exception as ex:
              st.toast(f"Error al eliminar usuario: {ex}", icon="❌")
        else:
          st.toast("Seleccione un usuario válido.", icon="⚠️")

      col_del_u_sel, col_del_u_btn = st.columns(
          [3, 1], vertical_alignment="bottom"
      )
      with col_del_u_sel:
        st.selectbox(
            "Seleccionar Usuario a Borrar",
            options=options_user_del,
            key="sel_user_eliminar",
        )
      with col_del_u_btn:
        st.button(
            "Eliminar Usuario",
            type="secondary",
            use_container_width=True,
            on_click=click_eliminar_usuario_sis,
            key="btn_del_user_item",
        )

  if rol_actual == "TIC":
    tab_cierre_idx = tab5
  else:
    tab_cierre_idx = tab5

  with tab_cierre_idx:
    st.subheader("Cierre de Proyecto y Reseteo Operativo")
    st.markdown("""
        Utilice esta herramienta al concluir un proyecto de fabricación. 
        Esto realiza automáticamente un respaldo histórico, limpia los registros transaccionales operativos, 
        reinicia contadores y optimiza la base de datos, manteniendo intacto su inventario maestro, operadores y accesos de usuarios.
        """)
    st.write("")
    confirmar_reset = st.checkbox(
        "Confirmo que deseo cerrar el proyecto actual y vaciar los registros"
        " transaccionales operativos."
    )
    if st.button(
        "Ejecutar Cierre y Reiniciar Base de Datos",
        type="primary",
        disabled=not confirmar_reset,
    ):
      exito, mensaje = cerrar_y_reiniciar_proyecto()
      if exito:
        st.success(mensaje)
        st.balloons()
      else:
        st.error(mensaje)

# =====================================================================
# MÓDULO 3: REPORTES Y ANALÍTICA PRO
# =====================================================================
elif menu == "REPORTES Y ANALÍTICA PRO":
  st.header("Reportes, KPIs y Consumos por Operadores")

  conn = get_connection()
  df_reg = pd.read_sql_query("SELECT * FROM registros_diarios", conn)
  df_hist = pd.read_sql_query("SELECT * FROM historial_entregas", conn)
  conn.close()

  if not df_reg.empty or not df_hist.empty:
    st.subheader("Indicadores Clave de Desempeño (KPIs)")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    total_metros_lineal = (
        df_reg["soldadura_lineal"].sum() if not df_reg.empty else 0.0
    )
    total_argon = df_reg["consumo_argon"].sum() if not df_reg.empty else 0
    total_punteos = df_reg["punteos"].sum() if not df_reg.empty else 0
    total_jornadas = len(df_reg)

    kpi1.metric("Soldadura Lineal Total", f"{total_metros_lineal:.2f} m")
    kpi2.metric("Argón Consumido", f"{total_argon} PSI")
    kpi3.metric("Punteos Totales", f"{total_punteos}")
    kpi4.metric("Jornadas Registradas", f"{total_jornadas}")

    st.write("---")
    st.subheader("Análisis de Consumo y Producción por Operador")

    col_op1, col_op2 = st.columns(2)
    with col_op1:
      st.markdown(
          "##### Producción en Soldadura (Metros Lineales por Soldador)"
      )
      if not df_reg.empty:
        df_prod_op = (
            df_reg.groupby("soldador")["soldadura_lineal"].sum().reset_index()
        )
        fig_prod = px.bar(
            df_prod_op,
            x="soldador",
            y="soldadura_lineal",
            text_auto=".2f",
            color_discrete_sequence=["#FF4B4B"],
        )
        fig_prod.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#fafafa"),
            xaxis=dict(title="Soldador", showgrid=False),
            yaxis=dict(
                title="Metros Lineales (m)",
                showgrid=True,
                gridcolor="#262730",
                rangemode="tozero",
            ),
            margin=dict(t=20, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_prod, use_container_width=True)
      else:
        st.info("Sin registros de soldadura.")

    with col_op2:
      st.markdown("##### Consumo de Argón (PSI por Soldador)")
      if not df_reg.empty:
        df_argon_op = (
            df_reg.groupby("soldador")["consumo_argon"].sum().reset_index()
        )
        fig_argon = px.bar(
            df_argon_op,
            x="soldador",
            y="consumo_argon",
            text_auto=True,
            color_discrete_sequence=["#FFA500"],
        )
        fig_argon.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#fafafa"),
            xaxis=dict(title="Soldador", showgrid=False),
            yaxis=dict(
                title="Consumo Argón (PSI)",
                showgrid=True,
                gridcolor="#262730",
                rangemode="tozero",
            ),
            margin=dict(t=20, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_argon, use_container_width=True)
      else:
        st.info("Sin registros de argón.")

    st.write("")
    st.markdown("##### Retiros de Insumos de Almacén por Operador")
    if not df_hist.empty:
      df_ins_op = (
          df_hist.groupby(["operador", "insumo"])["cantidad"]
          .sum()
          .reset_index()
      )
      st.dataframe(df_ins_op, use_container_width=True, hide_index=True)
    else:
      st.info("No hay entregas de insumos registradas todavía.")

    st.write("---")
    st.subheader("Registro Diario Detallado")
    st.dataframe(df_reg, use_container_width=True, hide_index=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df_reg.to_excel(writer, index=False, sheet_name="Registros Diarios")
      if not df_hist.empty:
        df_hist.to_excel(
            writer, index=False, sheet_name="Historial de Entregas"
        )
    excel_data = output.getvalue()

    st.download_button(
        label="Descargar Reporte Profesional en Excel (.xlsx)",
        data=excel_data,
        file_name=(
            "reporte_wuanaguanare_pro_"
            f"{datetime.now().strftime('%Y%m%d')}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        type="primary",
    )
  else:
    st.info(
        "No hay registros guardados todavía. Comienza a registrar jornadas y"
        " entregas en los menús anteriores."
    )
