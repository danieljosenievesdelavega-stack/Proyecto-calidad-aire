from __future__ import annotations
import plotly.graph_objects as go
import pydeck as pdk

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api import queries


def normalize_date(value):
    if value is None:
        return None
    if isinstance(value, str):
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if hasattr(value, "strftime"):
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    return pd.to_datetime(value).strftime("%Y-%m-%d")


@st.cache_data(ttl=300)
def load_latest_measurement_date():
    metadata = queries.pipeline_status()
    return normalize_date(metadata.get("fecha_max"))


st.set_page_config(

    page_title="Calidad del aire en Colombia",
    page_icon="🌎",
    layout="wide",
)
ocultar_elementos_ingles = """
    <style>
    /* Ocultar el botón Deploy en distintas versiones de Streamlit */
    .stDeployButton,
    .stAppDeployButton,
    [data-testid="stDeployButton"],
    [data-testid="stAppDeployButton"],
    button[title="Deploy"],
    button[aria-label="Deploy"] {
        display: none !important;
    }
    
    /* Ocultar el menú principal de Streamlit (tres puntos) */
    #MainMenu {visibility: hidden;}
    
    /* Ocultar el pie de página */
    footer {visibility: hidden;} 
    </style>
"""
st.markdown(ocultar_elementos_ingles, unsafe_allow_html=True)

# Contenido de la barra lateral
st.sidebar.header("Menú ")
st.sidebar.write("Selecciona un contaminante y ajusta los filtros.")

# Contenido principal
st.title("Panel Principal")


st.title("Monitoreo de contaminantes atmosféricos")
st.caption("Analítica descriptiva sobre mediciones horarias de estaciones en Colombia")

with st.sidebar:
    st.header("Filtros")
    contaminant = st.selectbox("Contaminante", queries.CONTAMINANTS, index=0)


@st.cache_data(ttl=300)
def load_summary(
    department: str | None,
    municipality: str | None,
    station_type: str | None,
    start_date: str | None,
    end_date: str | None,
    include_extremes: bool,
):
    return queries.summary(
        department=department,
        municipality=municipality,
        station_type=station_type,
        start_date=start_date,
        end_date=end_date,
        include_extremes=include_extremes,
    )


@st.cache_data(ttl=300)
def load_contaminants(
    department: str | None,
    municipality: str | None,
    station_type: str | None,
    start_date: str | None,
    end_date: str | None,
    include_extremes: bool,
):
    data = pd.DataFrame(
        queries.contaminants(
            department=department,
            municipality=municipality,
            station_type=station_type,
            start_date=start_date,
            end_date=end_date,
            include_extremes=include_extremes,
        ),
        columns=["contaminant", "records", "average", "minimum", "maximum"],
    )
    return data


@st.cache_data(ttl=300)
def load_locations(selected, department, municipality, station_type, start_date, end_date, include_extremes):
    return pd.DataFrame(
        queries.locations(
            contaminant=selected,
            department=department,
            municipality=municipality,
            station_type=station_type,
            start_date=start_date,
            end_date=end_date,
            include_extremes=include_extremes,
        )
    )


summary = load_summary(None, None, None, None, None, False)
fecha_max_metadata = load_latest_measurement_date() or "No disponible"
locations = load_locations(contaminant, None, None, None, None, None, False)

if locations.empty:
    st.warning(
        f"No hay mediciones con coordenadas disponibles para {contaminant}. "
        "Prueba con otro contaminante."
    )
    st.stop()

departments = ["Todos"] + sorted(
    locations["department"].dropna().unique().tolist()
)

with st.sidebar:
    min_date = pd.to_datetime(summary["start_date"]).date() if summary.get("start_date") else pd.Timestamp("2020-01-01").date()
    max_date = pd.to_datetime(summary["end_date"]).date() if summary.get("end_date") else pd.Timestamp("2024-12-31").date()
    selected_start_date = st.date_input(
        "Fecha inicial",
        min_value=min_date,
        max_value=max_date,
        value=min_date,
    )
    selected_end_date = st.date_input(
        "Fecha final",
        min_value=min_date,
        max_value=max_date,
        value=max_date,
    )

    if selected_start_date > selected_end_date:
        st.info("La fecha final debe ser igual o posterior a la fecha inicial.")
        st.stop()

    station_type = st.selectbox("Tipo de estación", ["Todos", "Fija", "Móvil"])
    include_extremes = st.toggle("Incluir mediciones marcadas como extremas", value=False)

    department = st.selectbox("Departamento", departments)

    filtered_locations = locations
    if department != "Todos":
        filtered_locations = locations[
            locations["department"] == department
        ]

    municipalities = ["Todos"] + sorted(
        filtered_locations["municipality"].dropna().unique().tolist()
    )

    municipality = st.selectbox("Municipio", municipalities)

    selected_department = None if department == "Todos" else department
    selected_municipality = None if municipality == "Todos" else municipality
    selected_station_type = None if station_type == "Todos" else station_type

@st.cache_data(ttl=300)
def load_stations(selected, limit, department, municipality, start_date, end_date, station_type, include_extremes):
    return pd.DataFrame(
        queries.stations(
            selected,
            limit,
            department,
            municipality,
            normalize_date(start_date),
            normalize_date(end_date),
            station_type,
            include_extremes,
        )
    )

@st.cache_data(ttl=300)
def load_station_count(selected, department, municipality, start_date, end_date, station_type, include_extremes):
    return queries.station_count(
        selected,
        department,
        municipality,
        normalize_date(start_date),
        normalize_date(end_date),
        station_type,
        include_extremes,
    )


@st.cache_data(ttl=300)
def load_trend(selected: str, department, municipality, station_type, start_date, end_date, include_extremes):
    return pd.DataFrame(
        queries.trend(
            selected,
            department=department,
            municipality=municipality,
            station_type=station_type,
            start_date=normalize_date(start_date),
            end_date=normalize_date(end_date),
            include_extremes=include_extremes,
        )
    )

@st.cache_data(ttl=300)
def load_anomalies(selected: str, department, municipality, station_type, start_date, end_date):
    return pd.DataFrame(
        queries.anomalies(
            selected,
            department=department,
            municipality=municipality,
            station_type=station_type,
            start_date=normalize_date(start_date),
            end_date=normalize_date(end_date),
        )
    )
@st.cache_data(ttl=300)
def load_anomaly_count(selected, department, municipality, station_type, start_date, end_date):
    return queries.anomaly_count(
        selected,
        department=department,
        municipality=municipality,
        station_type=station_type,
        start_date=normalize_date(start_date),
        end_date=normalize_date(end_date),
    )
# Agregar en app.py, junto a las otras funciones @st.cache_data:

@st.cache_data(ttl=300)
def load_alert_episodes(selected, department, municipality, start_date, end_date):
    return pd.DataFrame(
        queries.alert_episodes(
            selected,
            department=department,
            municipality=municipality,
            start_date=normalize_date(start_date),
            end_date=normalize_date(end_date),
        )
    )


@st.cache_data(ttl=300)
def load_alert_count(selected, department, municipality, start_date, end_date):
    return queries.alert_episode_count(
        selected,
        department=department,
        municipality=municipality,
        start_date=normalize_date(start_date),
        end_date=normalize_date(end_date),
    )


# Agregar junto a donde ya cargas "anomalies" y "anomaly_total":
alert_episodes = load_alert_episodes(
    contaminant, selected_department, selected_municipality,
    selected_start_date, selected_end_date,
)
alert_total = load_alert_count(
    contaminant, selected_department, selected_municipality,
    selected_start_date, selected_end_date,
)

# --- Nueva seccion, agregar despues del bloque de "Comparación entre contaminantes" ---

st.subheader(f"🚨 Alertas normativas de {contaminant} (Resolución 2254 de 2017)")

if alert_episodes.empty:
    st.success(f"No se registraron episodios de excedencia normativa para {contaminant} en el periodo seleccionado.")
else:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Episodios de excedencia", f"{alert_total:,}")

    def resaltar_severidad(fila):
        # >2x el limite = rojo fuerte, 1-2x = naranja
        color = "#ff4b4b" if fila["severity_ratio"] > 2 else "#ffa500"
        return [f"background-color: {color}33"] * len(fila)

    st.dataframe(
        alert_episodes.style.apply(resaltar_severidad, axis=1),
        use_container_width=True,
        hide_index=True,
        column_config={
            "start": st.column_config.DatetimeColumn("Inicio", format="DD/MM/YYYY HH:mm"),
            "end": st.column_config.DatetimeColumn("Fin", format="DD/MM/YYYY HH:mm"),
            "hours": st.column_config.NumberColumn("Horas"),
            "peak_value": st.column_config.NumberColumn("Pico (µg/m³)"),
            "legal_limit": st.column_config.NumberColumn("Límite legal"),
            "severity_ratio": st.column_config.NumberColumn("Veces sobre el límite", format="%.1fx"),
        },
    )
    st.caption(
        "🟧 Naranja: entre 1x y 2x el límite normativo · 🟥 Rojo: más de 2x el límite. "
        "Cada fila es un episodio continuo, no una medición individual."
    )

summary = load_summary(
    selected_department,
    selected_municipality,
    selected_station_type,
    normalize_date(selected_start_date),
    normalize_date(selected_end_date),
    include_extremes,
)
contaminant_data = load_contaminants(
    selected_department,
    selected_municipality,
    selected_station_type,
    normalize_date(selected_start_date),
    normalize_date(selected_end_date),
    include_extremes,
)
selected_data = contaminant_data[contaminant_data["contaminant"] == contaminant]
selected_average = (
    selected_data.iloc[0]["average"] if not selected_data.empty else None
)
station_max = load_station_count(
    contaminant,
    selected_department,
    selected_municipality,
    normalize_date(selected_start_date),
    normalize_date(selected_end_date),
    selected_station_type,
    include_extremes,
)

if station_max == 0:
    selected_scope = ""
    if selected_municipality:
        selected_scope = f" en {selected_municipality}, {selected_department}"
    elif selected_department:
        selected_scope = f" en {selected_department}"

    st.warning(
        f"No se encontraron registros con coordenadas para {contaminant}{selected_scope}. "
        "Prueba con otro contaminante o cambia los filtros."
    )
    st.stop()

if station_max == 1:
    station_limit = 1
    st.sidebar.caption("Estaciones en el mapa: 1")
else:
    station_limit = st.sidebar.slider(
        "Estaciones en el mapa",
        min_value=1,
        max_value=station_max,
        value=station_max,
        step=1,
        key=(
            f"station_limit_{contaminant}_"
            f"{selected_department or 'todos'}_"
            f"{selected_municipality or 'todos'}"
        ),
    )
stations = load_stations(
    contaminant,
    station_limit,
    selected_department,
    selected_municipality,
    normalize_date(selected_start_date),
    normalize_date(selected_end_date),
    selected_station_type,
    include_extremes,
)
trend = load_trend(
    contaminant,
    selected_department,
    selected_municipality,
    selected_station_type,
    normalize_date(selected_start_date),
    normalize_date(selected_end_date),
    include_extremes,
)
anomalies = load_anomalies(
    contaminant,
    selected_department,
    selected_municipality,
    selected_station_type,
    selected_start_date,
    selected_end_date,
)
anomaly_total = load_anomaly_count(
    contaminant,
    selected_department,
    selected_municipality,
    selected_station_type,
    selected_start_date,
    selected_end_date,
)

metric_columns = st.columns(4)
metric_columns[0].metric("Registros horarios", f"{summary['records']:,}")
metric_columns[1].metric("Estaciones", f"{summary['stations']:,}")
metric_columns[2].metric(
    "Promedio seleccionado",
    f"{selected_average:.2f}" if selected_average is not None else "Sin datos",
)
metric_columns[3].metric("Anomalías detectadas", f"{anomaly_total:,}")

st.subheader(f"Tendencia mensual de {contaminant}")

if trend.empty:
    st.warning("No hay datos de tendencia para este contaminante.")
else:
    trend["period"] = pd.to_datetime(trend["period"])
    trend = trend.sort_values("period")

    fig = go.Figure()

    # 1. Área sombreada entre el Promedio y el Percentil 95
    if len(trend) > 1:
        fig.add_trace(
            go.Scatter(
                x=pd.concat([trend["period"], trend["period"][::-1]]),
                y=pd.concat([trend["p95"], trend["average"][::-1]]),
                fill='toself',
                fillcolor='rgba(31, 119, 180, 0.15)',
                line=dict(color='rgba(255,255,255,0)'),
                hoverinfo="skip",
                showlegend=False,
                name="Rango P95-Promedio"
            )
        )

    # 2. Línea del Promedio
    fig.add_trace(
        go.Scatter(
            x=trend["period"],
            y=trend["average"],
            mode="lines+markers",
            name="Promedio",
            line=dict(width=3, color="#1f77b4"),
            marker=dict(size=8),
            hovertemplate=(
                "<b>%{x|%B %Y}</b><br>"
                "Promedio: %{y:.2f}<extra></extra>"
            ),
        )
    )

    # 3. Línea del Percentil 95
    fig.add_trace(
        go.Scatter(
            x=trend["period"],
            y=trend["p95"],
            mode="lines+markers",
            name="Percentil 95",
            line=dict(width=2, dash="dash", color="#ff7f0e"),
            marker=dict(size=8),
            hovertemplate=(
                "<b>%{x|%B %Y}</b><br>"
                "P95: %{y:.2f}<extra></extra>"
            ),
        )
    )

    # Configuración de diseño y layout
    fig.update_layout(
        xaxis_title="Fecha",
        yaxis_title="Concentración",
        hovermode="x unified",
        height=450,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,  # Ajustado para que no se traslape con el menú superior derecho
            xanchor="right",
            x=1,
        ),
    )

    fig.update_xaxes(
        tickformat="%b %Y",
        rangeslider_visible=(len(trend) > 5),  # Oculta el slider si hay pocos puntos
    )

    fig.update_yaxes(rangemode="tozero")

    st.plotly_chart(fig, use_container_width=True)

    # Aviso secundario si el rango es de solo un mes
    if len(trend) == 1:
        st.info("💡 Actualmente solo hay 1 mes de datos en el rango seleccionado. Amplía la consulta de fechas para visualizar la línea de tendencia.")

left, right = st.columns([1.25, 1])
with left:
    st.subheader("Estaciones por coordenadas")
    if stations.empty:
        st.info("No hay coordenadas disponibles para este filtro.")
    else:
        map_data = stations.rename(columns={"latitude": "lat", "longitude": "lon"}).copy()
 
        valor_min = map_data["average"].min()
        valor_max = map_data["average"].max()
        rango = (valor_max - valor_min) if valor_max > valor_min else 1
 
        # Escala amarillo (bajo) -> rojo (alto)
        def color_por_valor(v):
            proporcion = (v - valor_min) / rango
            return [255, int(255 * (1 - proporcion)), 40, 200]
 
        map_data["color"] = map_data["average"].apply(color_por_valor)
 
        capa = pdk.Layer(
            "ScatterplotLayer",
            data=map_data,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=2000,
            pickable=True,
            opacity=0.8,
        )

 
        vista = pdk.ViewState(
            latitude=map_data["lat"].mean(),
            longitude=map_data["lon"].mean(),
            zoom=4.5,
        )
 
        st.pydeck_chart(pdk.Deck(
            layers=[capa],
            initial_view_state=vista,
            tooltip={"text": "{station}\nPromedio: {average}"},
        ))
        st.caption(f"🟡 Menor concentración ({valor_min:.1f}) → 🔴 Mayor concentración ({valor_max:.1f})")
 
        st.dataframe(
            stations[["station", "municipality", "department", "average", "records"]],
            use_container_width=True,
            hide_index=True,
        )
with right:
    st.subheader(f"Top {len(anomalies)} valores anómalos más altos")
    if anomalies.empty:
        st.info("No hay resultados de anomalías para este contaminante.")
    else:
        anomalies["date"] = pd.to_datetime(anomalies["date"])
        st.dataframe(
            anomalies[["station", "department", "date", "value"]],
            use_container_width=True,
            hide_index=True,
        )

st.caption(
    f"Última medición disponible: {fecha_max_metadata}. "
    "Fuente: SISAIRE / datos.gov.co."
)

st.subheader("Comparación entre contaminantes")
st.dataframe(
    contaminant_data,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    f"Cobertura horaria: {summary['start_date']:%Y-%m-%d} a {summary['end_date']:%Y-%m-%d}. "
    "Los promedios usan registros marcados como horarios y válidos por el ETL."
)
