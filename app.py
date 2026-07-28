import base64
from datetime import datetime
import io
import os
import shutil
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# =====================================================================
# CONFIGURACIÓN DE LA PÁGINA
# =====================================================================
st.set_page_config(
    page_title="Wuanaguanare - Planta Madre",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Forzar idioma español en el DOM sin advertencias
st.html("<script>window.parent.document.documentElement.lang = 'es';</script>")

# =====================================================================
# CONFIGURACIÓN VISUAL PRO: CENTRADO DE LOGO Y LIMPIEZA DE UI
# =====================================================================
st.markdown(
    """
    <style>
        #MainMenu { visibility: hidden !important; display: none !important; }
        header[data-testid="stHeader"] { display: none !important; visibility: hidden !important; }
        footer { visibility: hidden !important; display: none !important; }
        [data-testid="stToolbar"] { display: none !important; visibility: hidden !important; }
        .stAppDeployButton { display: none !important; visibility: hidden !important; }
        [data-testid="stSidebarCollapseButton"], 
        [data-testid="collapsedControl"] { display: none !important; }
        
        /* Ocultar texto de ayuda "Press Enter to apply" en los inputs */
        [data-testid="InputInstructions"] { display: none !important; visibility: hidden !important; }
        
        /* Centrado absoluto y perfecto de todas las imágenes (logo) en body y sidebar */
        [data-testid="stImage"], section[data-testid="stSidebar"] [data-testid="stImage"] {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            width: 100% !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        [data-testid="stImage"] img, section[data-testid="stSidebar"] [data-testid="stImage"] img {
            display: block !important;
            margin-left: auto !important;
            margin-right: auto !important;
            float: none !important;
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
        [data-testid="stStatusWidget"] { visibility: hidden; display: none !important; }
        [data-testid="stDecoration"] { display: none !important; }
        div[class*="viewerBadge"] { 
            display: none !important; 
            visibility: hidden !important; 
        }
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# =====================================================================
# UTILIDADES DEL LOGO (Detección automática de nombres en GitHub)
# =====================================================================
def buscar_logo():
    nombres_posibles = [
        "logo_wuanaguanare.png", "logo_wuanaguanare.jpg", "logo_wuanaguanare.jpeg",
        "wuanaguanare.png", "wuanaguanare.jpg",
        "logo.png", "logo.jpg", "logo.jpeg", 
        "Logo.png", "Logo.jpg", "Logo.ico",
        "LOGO.png", "LOGO.PNG", "LOGO.JPG"
    ]
    for nombre in nombres_posibles:
        if os.path.exists(nombre):
            return nombre
    return None

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

        c.execute("""CREATE TABLE IF NOT EXISTS usuarios_sistema (
                      id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      usuario TEXT UNIQUE, 
                      password TEXT, 
                      rol TEXT)""")

        c.execute("SELECT COUNT(*) FROM usuarios_sistema")
        if c.fetchone()[0] == 0:
            c.executemany(
                "INSERT INTO usuarios_sistema (usuario, password, rol) VALUES (?, ?, ?)",
                [
                    ("tic", "admin123", "TIC"),
                    ("gerencia", "gerencia123", "Gerencia"),
                    ("almacen", "almacen123", "Almacén"),
                    ("seguimiento", "argon123", "Seguimiento"),
                ]
            )

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

        # Migraciones seguras
        c.execute("PRAGMA table_info(cilindros)")
        cols_cil = [col[1] for col in c.fetchall()]
        if "presion_inicial" not in cols_cil: c.execute("ALTER TABLE cilindros ADD COLUMN presion_inicial INTEGER DEFAULT 0")
        if "presion_actual" not in cols_cil: c.execute("ALTER TABLE cilindros ADD COLUMN presion_actual INTEGER DEFAULT 0")

        c.execute("PRAGMA table_info(inventario)")
        cols_inv = [col[1] for col in c.fetchall()]
        if "stock_minimo" not in cols_inv: c.execute("ALTER TABLE inventario ADD COLUMN stock_minimo REAL DEFAULT 0.0")
        if "costo_unitario" not in cols_inv: c.execute("ALTER TABLE inventario ADD COLUMN costo_unitario REAL DEFAULT 0.0")

        c.execute("PRAGMA table_info(registros_diarios)")
        cols_reg = [col[1] for col in c.fetchall()]
        if "soldadura_lineal" not in cols_reg: c.execute("ALTER TABLE registros_diarios ADD COLUMN soldadura_lineal REAL DEFAULT 0.0")
        if "soldadura_no_lineal" not in cols_reg: c.execute("ALTER TABLE registros_diarios ADD COLUMN soldadura_no_lineal REAL DEFAULT 0.0")
        if "punteos" not in cols_reg: c.execute("ALTER TABLE registros_diarios ADD COLUMN punteos INTEGER DEFAULT 0")
        if "tungstenos" not in cols_reg: c.execute("ALTER TABLE registros_diarios ADD COLUMN tungstenos INTEGER DEFAULT 0")
        if "varilla_gastada" not in cols_reg: c.execute("ALTER TABLE registros_diarios ADD COLUMN varilla_gastada REAL DEFAULT 0.0")
        if "orden_trabajo" not in cols_reg: c.execute("ALTER TABLE registros_diarios ADD COLUMN orden_trabajo TEXT DEFAULT 'GENERAL'")

        c.execute("PRAGMA table_info(historial_entregas)")
        cols_hist = [col[1] for col in c.fetchall()]
        if "codigo_insumo" not in cols_hist: c.execute("ALTER TABLE historial_entregas ADD COLUMN codigo_insumo TEXT")
        if "orden_trabajo" not in cols_hist: c.execute("ALTER TABLE historial_entregas ADD COLUMN orden_trabajo TEXT DEFAULT 'GENERAL'")

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error crítico al inicializar la base de datos: {e}")

init_db()

# =====================================================================
# SISTEMA DE AUTENTICACIÓN DINÁMICO
# =====================================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.rol = None

if not st.session_state.autenticado:
    st.markdown("""
        <style>
            body, html, [data-testid="stAppViewContainer"] {
                overflow: hidden !important;
            }
        </style>
    """, unsafe_allow_html=True)

    col_l1, col_l2, col_l3 = st.columns([1.5, 1.2, 1.5])
    with col_l2:
        st.markdown("<div style='margin-top: -15px;'></div>", unsafe_allow_html=True)
        
        ruta_logo = buscar_logo()
        if ruta_logo:
            st.image(ruta_logo, width=260)
        else:
            st.warning("⚠️ Falta el archivo del logo en GitHub.")

        st.markdown("<h2 style='text-align: center; margin: 0px 0px 0px 0px; font-size: 1.6rem;'>Wuanaguanare</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray; font-size: 0.8rem; margin: 2px 0px 10px 0px;'>Acceso Corporativo Seguro en la Nube</p>", unsafe_allow_html=True)

        usuario_input = st.text_input("Usuario", key="login_user")
        password_input = st.text_input("Contraseña", type="password", key="login_pass")

        st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
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

def cerrar_y_reiniciar_proyecto(directorio_respaldos="historico_db"):
    if not os.path.exists(directorio_respaldos):
        os.makedirs(directorio_respaldos)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_respaldo = os.path.join(directorio_respaldos, f"respaldo_proyecto_{timestamp}.sqlite")
    
    try:
        if os.path.exists("wuanaguanare_db.sqlite"):
            shutil.copy2("wuanaguanare_db.sqlite", ruta_respaldo)

        conn = get_connection()
        with conn:
            conn.execute("DELETE FROM registros_diarios;")
            conn.execute("DELETE FROM historial_entregas;")
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('registros_diarios', 'historial_entregas');")
        conn.close()

        conn_vacuum = sqlite3.connect("wuanaguanare_db.sqlite", check_same_thread=False)
        conn_vacuum.isolation_level = None
        conn_vacuum.execute("VACUUM;")
        conn_vacuum.close()

        return True, f"Proyecto cerrado. Histórico guardado en '{ruta_respaldo}' y tablas transaccionales restablecidas."
    except Exception as e:
        return False, f"Error crítico al intentar restablecer la base de datos: {e}"

# =====================================================================
# 2. MENÚ LATERAL Y CONTROL DE ROLES
# =====================================================================
ruta_logo_sidebar = buscar_logo()
if ruta_logo_sidebar:
    st.sidebar.image(ruta_logo_sidebar, use_container_width=True)
else:
    st.sidebar.title("WUANAGUANARE PMW")

st.sidebar.caption("Software Industrial en la Nube v2.7 Pro")

rol_actual = st.session_state.get("rol", "TIC")

if rol_actual == "TIC":
    opciones_menu = ["REGISTRO DIARIO GAS ARGÓN", "GESTIÓN DE PLANTA Y PROYECTOS", "REPORTES Y ANALÍTICA PRO"]
elif rol_actual == "Seguimiento":
    opciones_menu = ["REGISTRO DIARIO GAS ARGÓN", "REPORTES Y ANALÍTICA PRO"]
elif rol_actual == "Almacén":
    opciones_menu = ["GESTIÓN DE PLANTA Y PROYECTOS"]
elif rol_actual == "Gerencia":
    opciones_menu = ["REPORTES Y ANALÍTICA PRO"]
else:
    opciones_menu = ["REGISTRO DIARIO GAS ARGÓN"]

menu = st.sidebar.radio("Navegación", opciones_menu)

st.sidebar.write("---")
st.sidebar.markdown(f"Conectado como: **{rol_actual}**")
if st.sidebar.button("Cerrar Sesión", use_container_width=True, type="secondary"):
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
            file_name=f"backup_wuanaguanare_{datetime.now().strftime('%Y%m%d_%H%M')}.sqlite",
            mime="application/x-sqlite3",
            use_container_width=True,
        )

conn = get_connection()
df_stock_check = pd.read_sql_query(
    "SELECT insumo, cantidad, stock_minimo, unidad FROM inventario WHERE stock_minimo > 0 AND cantidad <= stock_minimo",
    conn,
)
conn.close()

if not df_stock_check.empty:
    st.sidebar.error("¡Atención! Insumos en Stock Crítico:")
    for _, row in df_stock_check.iterrows():
        st.sidebar.markdown(f"- **{row['insumo']}**: {row['cantidad']} {row['unidad']} (Mín: {row['stock_minimo']})")

# =====================================================================
# MÓDULO 1: REGISTRO DIARIO
# =====================================================================
if menu == "REGISTRO DIARIO GAS ARGÓN":
    st.header("Registro Diario Gas Argón y Producción")

    conn = get_connection()
    cilindros_df = pd.read_sql_query("SELECT nombre, presion_actual FROM cilindros", conn)
    operadores_df = pd.read_sql_query("SELECT nombre FROM operadores", conn)
    conn.close()

    dict_presiones = dict(zip(cilindros_df["nombre"], cilindros_df["presion_actual"])) if not cilindros_df.empty else {}
    lista_cilindros = list(dict_presiones.keys())
    lista_operadores = operadores_df["nombre"].tolist() if not operadores_df.empty else []

    options_cilindros = ["-- Seleccione un cilindro --"] + lista_cilindros if lista_cilindros else ["Sin cilindros registrados"]
    options_operadores = ["-- Seleccione un operador --"] + lista_operadores if lista_operadores else ["Sin operadores registrados"]

    cilindro_activo = st.selectbox("Cilindro Activo", options=options_cilindros)

    if cilindro_activo and cilindro_activo not in ["-- Seleccione un cilindro --", "Sin cilindros registrados"]:
        presion_actual_cil = dict_presiones.get(cilindro_activo, 0)
        st.info(f"Argón disponible en **{cilindro_activo}**: **{presion_actual_cil} PSI**")

    with st.form(key="form_registro_diario", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            soldador = st.selectbox("Soldador / Operador", options=options_operadores)
            orden_trabajo = st.text_input("Orden de Trabajo / Proyecto (Ej: OT-2026-04)", value="GENERAL")
            p_cierre = st.number_input("Presión Cierre (PSI)", min_value=0, value=0)
        with col2:
            soldadura_lineal = st.number_input("Soldadura Lineal (m)", min_value=0.0, value=0.0, format="%.2f")
            soldadura_no_lineal = st.number_input("Soldadura No Lineal (m)", min_value=0.0, value=0.0, format="%.2f")
            punteos = st.number_input("Punteos (Cantidad)", min_value=0, value=0)
            tungstenos = st.number_input("Tungstenos gastados", min_value=0, value=0)

        st.write("")
        submitted_jornada = st.form_submit_button("Guardar Jornada", type="primary", use_container_width=True)

        if submitted_jornada:
            if not cilindro_activo or cilindro_activo in ["-- Seleccione un cilindro --", "Sin cilindros registrados"]:
                st.error("Debe seleccionar un cilindro válido en la lista desplegable.")
            elif not soldador or soldador in ["-- Seleccione un operador --", "Sin operadores registrados"]:
                st.error("Debe seleccionar un operador válido en la lista desplegable.")
            else:
                p_inicio_actual = int(dict_presiones.get(cilindro_activo, 0))
                if p_cierre > p_inicio_actual:
                    st.error(f"La presión de cierre ({p_cierre} PSI) no puede ser mayor que la presión inicial disponible ({p_inicio_actual} PSI).")
                else:
                    consumo_argon = p_inicio_actual - p_cierre
                    consumo_varilla = soldadura_lineal * 23.0

                    conn = get_connection()
                    try:
                        with conn:
                            c = conn.cursor()
                            c.execute(
                                """INSERT INTO registros_diarios 
                                   (fecha, cilindro, soldador, presion_inicio, presion_cierre, consumo_argon, soldadura_lineal, soldadura_no_lineal, punteos, tungstenos, varilla_gastada, orden_trabajo) 
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cilindro_activo, soldador,
                                    int(p_inicio_actual), int(p_cierre), int(consumo_argon), float(soldadura_lineal),
                                    float(soldadura_no_lineal), int(punteos), int(tungstenos), float(consumo_varilla),
                                    orden_trabajo.strip().upper(),
                                ),
                            )
                            c.execute("UPDATE cilindros SET presion_actual = ? WHERE nombre = ?", (int(p_cierre), cilindro_activo))
                        st.session_state["toast_jornada"] = f"Jornada guardada. OT: {orden_trabajo.upper()} | Consumo argón: {consumo_argon} PSI"
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
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cilindros", "Inventario e Insumos", "Operadores", "Gestión de Usuarios", "Cierre de Proyecto"])
    else:
        tab1, tab2, tab3, tab5 = st.tabs(["Cilindros", "Inventario e Insumos", "Operadores", "Cierre de Proyecto"])

    # --- TAB 1: CILINDROS ---
    with tab1:
        st.subheader("Control de Cilindros de Argón")
        nombre_cilindro = st.text_input("Nombre / Código del Cilindro", key="input_nom_cil")
        presion_ini = st.number_input("Presión Inicial (PSI)", min_value=0, value=0, key="input_presion_cil")

        if st.button("Registrar Cilindro", key="btn_reg_cilindro"):
            if nombre_cilindro.strip() != "":
                try:
                    conn = get_connection()
                    with conn:
                        c = conn.cursor()
                        c.execute("INSERT INTO cilindros (nombre, presion_inicial, presion_actual) VALUES (?, ?, ?)",
                                  (nombre_cilindro.strip().upper(), int(presion_ini), int(presion_ini)))
                    conn.close()
                    st.toast(f"Cilindro {nombre_cilindro.strip().upper()} agregado correctamente.", icon="✅")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.toast("Este cilindro ya se encuentra registrado.", icon="⚠️")
                except Exception as ex:
                    st.toast(f"Error al registrar cilindro: {ex}", icon="❌")
            else:
                st.toast("Debe ingresar un nombre o código de cilindro válido.", icon="⚠️")

        st.write("---")
        st.subheader("Eliminar Cilindro")
        conn = get_connection()
        df_cil = pd.read_sql_query("SELECT id, nombre, presion_inicial, presion_actual FROM cilindros", conn)
        conn.close()

        lista_cils_del = df_cil["nombre"].tolist() if not df_cil.empty else []
        options_cil_del = ["-- Seleccione un cilindro --"] + lista_cils_del

        def click_eliminar_cilindro():
            cil_seleccionado = st.session_state.get("sel_cil_eliminar")
            if cil_seleccionado and cil_seleccionado != "-- Seleccione un cilindro --":
                try:
                    conn = get_connection()
                    with conn:
                        conn.execute("DELETE FROM cilindros WHERE nombre = ?", (cil_seleccionado,))
                    conn.close()
                    st.toast(f"Cilindro {cil_seleccionado} eliminado exitosamente.", icon="✅")
                except Exception as ex:
                    st.toast(f"Error al eliminar: {ex}", icon="❌")
            else:
                st.toast("Seleccione un cilindro válido.", icon="⚠️")

        col_del_cil_sel, col_del_cil_btn = st.columns([3, 1], vertical_alignment="bottom")
        with col_del_cil_sel:
            st.selectbox("Seleccionar Cilindro", options=options_cil_del, key="sel_cil_eliminar")
        with col_del_cil_btn:
            st.button("Eliminar", type="secondary", use_container_width=True, on_click=click_eliminar_cilindro, key="btn_del_cilindro")

        st.write("")
        conn = get_connection()
        df_cil_actualizado = pd.read_sql_query("SELECT * FROM cilindros", conn)
        conn.close()
        st.dataframe(df_cil_actualizado, hide_index=True)

    # --- TAB 2: INVENTARIO E INSUMOS ---
    with tab2:
        st.subheader("Gestión de Inventario e Insumos")
        unidad_seleccionada = st.selectbox("Unidad de Medida Principal", options=["kg", "g", "Unidad", "Litros", "Metros", "Pares"], key="select_unidad_stock")

        with st.form(key="form_inventario", clear_on_submit=True):
            col_inv1, col_inv2, col_inv3 = st.columns(3)
            with col_inv1:
                cod_ins = st.text_input("Código o Lote del Insumo")
                nombre_insumo = st.text_input("Nombre del Artículo")
            with col_inv2:
                if unidad_seleccionada in ["Unidad", "Pares"]:
                    cant_ins = st.number_input("Cantidad a Agregar", min_value=0, value=0, step=1, format="%d")
                    stock_min = st.number_input("Stock Mínimo Alerta", min_value=0, value=0, step=1, format="%d")
                else:
                    cant_ins = st.number_input("Cantidad a Agregar", min_value=0.0, value=0.0, format="%.2f")
                    stock_min = st.number_input("Stock Mínimo Alerta", min_value=0.0, value=0.0, format="%.2f")
            with col_inv3:
                costo_unit = st.number_input("Costo Unitario ($)", min_value=0.0, value=0.0, format="%.2f")
                st.write("")
                st.write("")
                submitted = st.form_submit_button("Sumar / Guardar en Inventario", type="primary", use_container_width=True)

            if submitted:
                if cod_ins.strip() == "" or nombre_insumo.strip() == "":
                    st.error("Debe ingresar código/lote y nombre del artículo.")
                else:
                    try:
                        conn = get_connection()
                        with conn:
                            c = conn.cursor()
                            c.execute(
                                """INSERT INTO inventario (codigo, insumo, cantidad, unidad, stock_minimo, costo_unitario) 
                                   VALUES (?, ?, ?, ?, ?, ?)
                                   ON CONFLICT(codigo) DO UPDATE SET
                                       insumo = excluded.insumo,
                                       cantidad = inventario.cantidad + excluded.cantidad,
                                       unidad = excluded.unidad,
                                       stock_minimo = excluded.stock_minimo,
                                       costo_unitario = excluded.costo_unitario""",
                                (cod_ins.strip().upper(), nombre_insumo.strip().upper(), float(cant_ins), unidad_seleccionada, float(stock_min), float(costo_unit)),
                            )
                        conn.close()
                        st.session_state["toast_msg"] = f"Inventario actualizado: se agregaron {cant_ins} {unidad_seleccionada} a '{nombre_insumo.strip().upper()}'."
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error: {ex}")

        if "toast_msg" in st.session_state:
            st.toast(st.session_state["toast_msg"], icon="✅")
            del st.session_state["toast_msg"]

        st.write("")
        st.subheader("Estado Actual del Inventario")
        conn = get_connection()
        df_inv = pd.read_sql_query("SELECT codigo, insumo, cantidad, unidad, stock_minimo, costo_unitario FROM inventario", conn)
        conn.close()
        if not df_inv.empty:
            st.dataframe(df_inv, hide_index=True)
        else:
            st.info("No hay insumos registrados en el inventario.")

        st.write("---")
        st.subheader("Registrar Entrega o Asignación de Insumo a Operador")
        conn = get_connection()
        df_inv_act = pd.read_sql_query("SELECT codigo, insumo, cantidad, unidad FROM inventario", conn)
        df_ops_act = pd.read_sql_query("SELECT nombre FROM operadores", conn)
        conn.close()

        lista_codigos_inv = df_inv_act["codigo"].tolist() if not df_inv_act.empty else []
        options_entrega_inv = ["-- Seleccione un insumo --"] + lista_codigos_inv
        lista_nombres_ops = df_ops_act["nombre"].tolist() if not df_ops_act.empty else []
        options_entrega_ops = ["-- Seleccione un operador --"] + lista_nombres_ops

        insumo_elegido = st.selectbox("Insumo del Inventario", options=options_entrega_inv, key="select_insumo_entrega")
        
        stock_actual = 0.0
        unidad_art_base = "kg"
        if insumo_elegido != "-- Seleccione un insumo --":
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT insumo, cantidad, unidad FROM inventario WHERE codigo = ?", (insumo_elegido,))
            res_u = c.fetchone()
            conn.close()
            if res_u:
                nombre_art_base, stock_actual, unidad_art_base = res_u

        if unidad_art_base == "kg": unidades_posibles_retiro = ["g", "kg"]
        elif unidad_art_base == "g": unidades_posibles_retiro = ["g", "kg"]
        elif unidad_art_base in ["Metros", "m"]: unidades_posibles_retiro = ["cm", "Metros"]
        elif unidad_art_base in ["Litros", "l"]: unidades_posibles_retiro = ["ml", "Litros"]
        else: unidades_posibles_retiro = [unidad_art_base]

        col_ent1, col_ent2, col_ent3, col_ent4 = st.columns(4)
        with col_ent1:
            operador_elegido = st.selectbox("Operador Asignado", options=options_entrega_ops, key="ent_op")
        with col_ent2:
            ot_entrega = st.text_input("Orden de Trabajo / OT", value="GENERAL", key="ent_ot")
        with col_ent3:
            unidad_retiro = st.selectbox("Unidad de Retiro", options=unidades_posibles_retiro, key="ent_unidad")
        with col_ent4:
            if unidad_retiro in ["Unidad", "Pares"]:
                cant_entrega = st.number_input("Cantidad", min_value=0, value=0, step=1, format="%d", key="ent_cant_int")
            else:
                cant_entrega = st.number_input("Cantidad", min_value=0.0, value=0.0, format="%.2f", key="ent_cant_float")

        cant_a_descontar = float(cant_entrega)
        if unidad_art_base == "kg" and unidad_retiro == "g": cant_a_descontar = float(cant_entrega) / 1000.0
        elif unidad_art_base == "g" and unidad_retiro == "kg": cant_a_descontar = float(cant_entrega) * 1000.0
        elif unidad_art_base in ["Metros", "m"] and unidad_retiro == "cm": cant_a_descontar = float(cant_entrega) / 100.0
        elif unidad_art_base in ["Litros", "l"] and unidad_retiro == "ml": cant_a_descontar = float(cant_entrega) / 1000.0

        if insumo_elegido != "-- Seleccione un insumo --":
            st.info(f"Stock disponible en almacén: **{stock_actual} {unidad_art_base}**")
            if cant_a_descontar > stock_actual:
                st.warning(f"**¡Alerta de Stock Insuficiente!** Estás solicitando {cant_entrega} {unidad_retiro}, pero solo tienes **{stock_actual} {unidad_art_base}** disponible.")

        if st.button("Registrar Entrega", type="primary", use_container_width=True, key="btn_reg_entrega_direct"):
            if insumo_elegido == "-- Seleccione un insumo --": st.error("Debe seleccionar un insumo válido.")
            elif operador_elegido == "-- Seleccione un operador --": st.error("Debe seleccionar un operador válido.")
            elif cant_entrega <= 0: st.error("La cantidad debe ser mayor a cero.")
            elif cant_a_descontar > stock_actual: st.error(f"Stock insuficiente. Solo tienes {stock_actual} {unidad_art_base} disponible.")
            else:
                try:
                    conn = get_connection()
                    with conn:
                        c = conn.cursor()
                        nuevo_stock = stock_actual - cant_a_descontar
                        c.execute("UPDATE inventario SET cantidad = ? WHERE codigo = ?", (nuevo_stock, insumo_elegido))
                        c.execute(
                            """INSERT INTO historial_entregas (fecha, codigo_insumo, insumo, cantidad, unidad, operador, orden_trabajo)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), insumo_elegido, nombre_art_base, float(cant_entrega), unidad_retiro, operador_elegido, ot_entrega.strip().upper()),
                        )
                    conn.close()
                    st.session_state["toast_entrega"] = f"Entrega de {cant_entrega} {unidad_retiro} de '{nombre_art_base}' a {operador_elegido} registrada con éxito."
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al registrar la entrega: {ex}")

        if "toast_entrega" in st.session_state:
            st.toast(st.session_state["toast_entrega"], icon="✅")
            del st.session_state["toast_entrega"]

    # --- TAB 3: OPERADORES ---
    with tab3:
        st.subheader("Control de Operadores")
        col_op1, col_op2 = st.columns([3, 1], vertical_alignment="bottom")
        with col_op1:
            nuevo_operador = st.text_input("Nombre del Nuevo Operador", key="input_nuevo_op")
        with col_op2:
            if st.button("Registrar Operador", key="btn_reg_op", use_container_width=True):
                if nuevo_operador.strip() != "":
                    try:
                        conn = get_connection()
                        with conn:
                            conn.execute("INSERT INTO operadores (nombre) VALUES (?)", (nuevo_operador.strip().upper(),))
                        conn.close()
                        st.toast(f"Operador {nuevo_operador.strip().upper()} registrado correctamente.", icon="✅")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.toast("Este operador ya se encuentra registrado.", icon="⚠️")
                    except Exception as ex:
                        st.toast(f"Error al registrar operador: {ex}", icon="❌")
                else:
                    st.toast("Debe ingresar un nombre válido.", icon="⚠️")

        st.write("---")
        st.subheader("Operadores Activos")
        conn = get_connection()
        df_operadores = pd.read_sql_query("SELECT id, nombre FROM operadores", conn)
        conn.close()
        
        if not df_operadores.empty:
            st.dataframe(df_operadores, hide_index=True, use_container_width=True)
        else:
            st.info("No hay operadores registrados actualmente.")

    # --- TAB 4: USUARIOS (Solo TIC) ---
    if rol_actual == "TIC":
        with tab4:
            st.subheader("Gestión de Usuarios del Sistema")
            with st.form(key="form_usuarios", clear_on_submit=True):
                col_u1, col_u2, col_u3 = st.columns(3)
                with col_u1:
                    nuevo_usuario = st.text_input("Nuevo Usuario (minúsculas)")
                with col_u2:
                    nuevo_pass = st.text_input("Contraseña", type="password")
                with col_u3:
                    rol_usuario = st.selectbox("Rol del Sistema", ["TIC", "Gerencia", "Almacén", "Seguimiento"])
                
                st.write("")
                submit_user = st.form_submit_button("Crear / Actualizar Usuario", type="primary")
                
                if submit_user:
                    if nuevo_usuario.strip() and nuevo_pass.strip():
                        try:
                            conn = get_connection()
                            with conn:
                                conn.execute(
                                    """INSERT INTO usuarios_sistema (usuario, password, rol) VALUES (?, ?, ?)
                                       ON CONFLICT(usuario) DO UPDATE SET password = excluded.password, rol = excluded.rol""",
                                    (nuevo_usuario.strip().lower(), nuevo_pass.strip(), rol_usuario),
                                )
                            conn.close()
                            st.success(f"Usuario '{nuevo_usuario.strip().lower()}' procesado exitosamente.")
                        except Exception as e:
                            st.error(f"Error al gestionar usuario: {e}")
                    else:
                        st.error("Complete todos los campos (Usuario y Contraseña).")
            
            st.write("---")
            st.subheader("Usuarios Registrados")
            conn = get_connection()
            df_users = pd.read_sql_query("SELECT id, usuario, rol FROM usuarios_sistema", conn)
            conn.close()
            st.dataframe(df_users, hide_index=True, use_container_width=True)

    # --- TAB 5: CIERRE DE PROYECTO ---
    with tab5:
        st.subheader("Cierre de Proyecto y Mantenimiento de Base de Datos")
        st.warning("⚠️ **¡ACCIÓN IRREVERSIBLE!**\n\nEsta acción creará un respaldo histórico de la base de datos actual y luego **borrará todos los registros transaccionales** (Registros diarios e Historial de entregas). El inventario, operadores, cilindros y usuarios permanecerán intactos.")
        
        clave_confirmacion = st.text_input("Para proceder, escriba la palabra 'CONFIRMAR' en mayúsculas:", key="input_confirm")
        
        if clave_confirmacion == "CONFIRMAR":
            if st.button("EJECUTAR CIERRE DE PROYECTO", type="primary", use_container_width=True):
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
    st.header("Dashboard Analítico y Reportes")

    tab_rep1, tab_rep2, tab_rep3 = st.tabs(["Consumo Diario y Soldadura", "Historial de Entregas Almacén", "Estado General de Inventario"])

    with tab_rep1:
        st.subheader("Registros Diarios de Operaciones (Gas y Soldadura)")
        conn = get_connection()
        df_diario = pd.read_sql_query("SELECT * FROM registros_diarios ORDER BY id DESC", conn)
        conn.close()

        if not df_diario.empty:
            st.dataframe(df_diario, hide_index=True, use_container_width=True)
            st.write("---")
            st.subheader("Analítica de Consumo y Producción")
            
            # Fila 1 de gráficos (Argón)
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                df_consumo = df_diario.groupby("fecha")["consumo_argon"].sum().reset_index()
                if not df_consumo.empty:
                    fig_consumo = px.line(df_consumo, x="fecha", y="consumo_argon", title="Consumo de Argón (PSI) por Registro", markers=True)
                    fig_consumo.update_layout(xaxis_title="Fecha / Hora", yaxis_title="Consumo (PSI)")
                    st.plotly_chart(fig_consumo, use_container_width=True)

            with col_chart2:
                df_soldador = df_diario.groupby("soldador")["consumo_argon"].sum().reset_index()
                if not df_soldador.empty:
                    fig_soldador = px.bar(
                        df_soldador, 
                        x="soldador", 
                        y="consumo_argon", 
                        title="Total Consumo de Argón por Operador", 
                        color="soldador",
                        text="consumo_argon"
                    )
                    fig_soldador.update_traces(width=0.35, textposition='auto')
                    fig_soldador.update_layout(xaxis_title="Operador", yaxis_title="Consumo (PSI)")
                    st.plotly_chart(fig_soldador, use_container_width=True)

            # Fila 2 de gráficos (Metros de Soldadura Lineal y No Lineal) - RESTAURADO
            st.write("---")
            col_chart3, col_chart4 = st.columns(2)
            with col_chart3:
                df_soldadura_op = df_diario.groupby("soldador")[["soldadura_lineal", "soldadura_no_lineal"]].sum().reset_index()
                if not df_soldadura_op.empty:
                    fig_w_op = px.bar(
                        df_soldadura_op,
                        x="soldador",
                        y=["soldadura_lineal", "soldadura_no_lineal"],
                        title="Metros de Soldadura (Lineal y No Lineal) por Operador",
                        barmode="group",
                        text_auto=True
                    )
                    fig_w_op.update_layout(xaxis_title="Operador", yaxis_title="Metros (m)")
                    st.plotly_chart(fig_w_op, use_container_width=True)

            with col_chart4:
                df_soldadura_date = df_diario.groupby("fecha")[["soldadura_lineal", "soldadura_no_lineal"]].sum().reset_index()
                if not df_soldadura_date.empty:
                    fig_w_date = px.line(
                        df_soldadura_date,
                        x="fecha",
                        y=["soldadura_lineal", "soldadura_no_lineal"],
                        title="Evolución Temporal de Soldadura (Metros)",
                        markers=True
                    )
                    fig_w_date.update_layout(xaxis_title="Fecha / Hora", yaxis_title="Metros (m)")
                    st.plotly_chart(fig_w_date, use_container_width=True)
                    
            csv_diario = df_diario.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar Reporte Diario (CSV)", csv_diario, "reporte_produccion_diaria.csv", "text/csv", use_container_width=True)
        else:
            st.info("No existen registros diarios de operaciones en este momento.")

    with tab_rep2:
        st.subheader("Historial de Movimientos y Entregas de Almacén")
        conn = get_connection()
        df_entregas = pd.read_sql_query("SELECT * FROM historial_entregas ORDER BY id DESC", conn)
        conn.close()

        if not df_entregas.empty:
            st.dataframe(df_entregas, hide_index=True, use_container_width=True)
            st.write("---")
            col_ent1, col_ent2 = st.columns(2)
            
            with col_ent1:
                df_entregas_ot = df_entregas.groupby("orden_trabajo").size().reset_index(name='cantidad_movimientos')
                fig_ot = px.pie(df_entregas_ot, values='cantidad_movimientos', names='orden_trabajo', title="Distribución de Entregas por Orden de Trabajo (OT)")
                st.plotly_chart(fig_ot, use_container_width=True)
                
            with col_ent2:
                df_entregas_op = df_entregas.groupby("operador").size().reset_index(name='cantidad_retiros')
                fig_op = px.bar(
                    df_entregas_op, 
                    x='operador', 
                    y='cantidad_retiros', 
                    title="Cantidad de Retiros de Almacén por Operador", 
                    color='operador',
                    text='cantidad_retiros'
                )
                fig_op.update_traces(width=0.35, textposition='auto')
                fig_op.update_layout(xaxis_title="Operador", yaxis_title="Cantidad Retiros")
                st.plotly_chart(fig_op, use_container_width=True)
            
            csv_entregas = df_entregas.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar Historial de Entregas (CSV)", csv_entregas, "historial_entregas_almacen.csv", "text/csv", use_container_width=True)
        else:
            st.info("No hay entregas registradas en el historial.")
            
    with tab_rep3:
        st.subheader("Estado Valorizado del Inventario")
        conn = get_connection()
        df_inv_rep = pd.read_sql_query("SELECT codigo, insumo, cantidad, unidad, stock_minimo, costo_unitario FROM inventario", conn)
        conn.close()

        if not df_inv_rep.empty:
            df_inv_rep["valor_total"] = df_inv_rep["cantidad"] * df_inv_rep["costo_unitario"]
            valor_total_inventario = df_inv_rep["valor_total"].sum()
            
            st.metric("Valor Total del Inventario ($)", f"${valor_total_inventario:,.2f}")
            
            st.dataframe(
                df_inv_rep, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "costo_unitario": st.column_config.NumberColumn("Costo Unit. ($)", format="$%.2f"),
                    "valor_total": st.column_config.NumberColumn("Valor Total ($)", format="$%.2f")
                }
            )
            
            csv_inv = df_inv_rep.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar Estado de Inventario (CSV)", csv_inv, "estado_inventario_valorizado.csv", "text/csv", use_container_width=True)
        else:
            st.info("El inventario se encuentra vacío.")
