import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import altair as alt
from datetime import datetime

# --- Dashboard Configuration ---
st.set_page_config(page_title="Tree Dashboard", layout="wide")
PRIMARY_COLOR = "#A7C7E7"
DARK_COLOR = "#2C2C2C"

st.markdown(f"""
    <style>
    .element-container .stMetric label {{
        color: {DARK_COLOR};
        font-weight: 600;
    }}
    .element-container .stMetric div {{
        color: {DARK_COLOR};
        font-size: 1.3em;
    }}
    </style>
""", unsafe_allow_html=True)


# --- Load CSV Data ---
@st.cache_data
def load_csv_data(neighbourhood):
    df = pd.read_csv("data/public-trees.csv", sep=";")
    df = df[df["NEIGHBOURHOOD_NAME"].str.upper() == neighbourhood.upper()]
    return df

# --- Fetch API Data ---
@st.cache_data(ttl=3600)
def fetch_api_data(neighbourhood):
    base_url = "https://opendata.vancouver.ca"
    api_path = "/api/explore/v2.1/catalog/datasets/public-trees/records"
    all_results = []
    offset, limit, MAX = 0, 100, 10000
    while offset < MAX:
        url = f"{base_url}{api_path}?limit={limit}&offset={offset}&where=neighbourhood_name='{neighbourhood}'"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            results = data.get('results', [])
            all_results.extend(results)
            if len(results) < limit:
                break
            offset += limit
        except Exception as e:
            st.error(f"API Error: {e}")
            break
    return pd.json_normalize(all_results)

# --- Parse Data ---
def parse_data(df):
    # Normalize column names to uppercase
    df.columns = [col.upper() for col in df.columns]

    # Location parsing
    if 'GEO_POINT_2D' in df.columns:
        coords = df['GEO_POINT_2D'].str.split(',', expand=True)
        df['LATITUDE'] = pd.to_numeric(coords[0], errors='coerce')
        df['LONGITUDE'] = pd.to_numeric(coords[1], errors='coerce')
    elif 'GEOM.GEOMETRY.COORDINATES' in df.columns:
        df['LATITUDE'] = df['GEOM.GEOMETRY.COORDINATES'].apply(lambda x: x[1] if isinstance(x, list) and len(x) == 2 else None)
        df['LONGITUDE'] = df['GEOM.GEOMETRY.COORDINATES'].apply(lambda x: x[0] if isinstance(x, list) and len(x) == 2 else None)
    else:
        df['LATITUDE'] = None
        df['LONGITUDE'] = None

    # Standardize and fill missing fields
    df['COMMON_NAME'] = df['COMMON_NAME'].fillna('Unknown') if 'COMMON_NAME' in df else 'Unknown'
    df['SPECIES_NAME'] = df['SPECIES_NAME'].fillna('Unknown') if 'SPECIES_NAME' in df else 'Unknown'
    df['HEIGHT_RANGE'] = df['HEIGHT_RANGE'].fillna('Unknown') if 'HEIGHT_RANGE' in df else 'Unknown'
    df['DIAMETER'] = pd.to_numeric(df['DIAMETER'], errors='coerce') if 'DIAMETER' in df else None
    df['DATE_PLANTED'] = pd.to_datetime(df['DATE_PLANTED'], errors='coerce') if 'DATE_PLANTED' in df else None
    df['PLANT_YEAR'] = df['DATE_PLANTED'].apply(lambda x: x.year if pd.notnull(x) else None)

    # Assign lowercase columns for UI
    df['common_name'] = df['COMMON_NAME']
    df['species_name'] = df['SPECIES_NAME']
    df['height_range'] = df['HEIGHT_RANGE']
    df['diameter'] = df['DIAMETER']
    df['plant_date'] = df['DATE_PLANTED']
    df['plant_year'] = df['PLANT_YEAR']
    df['latitude'] = df['LATITUDE']
    df['longitude'] = df['LONGITUDE']

    return df.dropna(subset=['latitude', 'longitude'])

# --- Create Map ---
def create_map(df, highlight=None):
    if df.empty:
        return folium.Map(location=[49.2827, -123.1207], zoom_start=12)
    m = folium.Map(location=[df['latitude'].mean(), df['longitude'].mean()], zoom_start=14, tiles="CartoDB Positron")
    for _, row in df.iterrows():
        if pd.notnull(row['latitude']) and pd.notnull(row['longitude']):
            color = PRIMARY_COLOR if highlight and row['common_name'] == highlight else 'green'
            tooltip = f"<b>{row['common_name']}</b><br>Species: {row['species_name']}<br>Planted: {row['plant_date'].date() if pd.notnull(row['plant_date']) else 'Unknown'}"
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=6, color=color, fill=True, fill_color=color, fill_opacity=0.7, tooltip=tooltip
            ).add_to(m)
    return m

# --- UI Layout ---
st.title("🌳 Vancouver Trees Dashboard")
data_source = st.selectbox("Select Data Source", ["", "CSV (faster, local file)", "API (live city data)"])
neighbourhoods = ["", "ARBUTUS RIDGE", "DOWNTOWN", "DUNBAR-SOUTHLANDS", "FAIRVIEW",
    "GRANDVIEW-WOODLAND", "HASTINGS-SUNRISE", "KENSINGTON-CEDAR COTTAGE", "KERRISDALE",
    "KILLARNEY", "KITSILANO", "MARPOLE", "MOUNT PLEASANT", "OAKRIDGE", "RENFREW-COLLINGWOOD",
    "RILEY PARK", "SHAUGHNESSY", "SOUTH CAMBIE", "STRATHCONA", "SUNSET", "VICTORIA-FRASERVIEW",
    "WEST END", "WEST POINT GREY"]
selected = st.selectbox("Select Neighbourhood", neighbourhoods)

if data_source and selected:
    with st.spinner("Loading data..."):
        if "CSV" in data_source:
            df = load_csv_data(selected)
        elif "API" in data_source:
            df = fetch_api_data(selected)

        df = parse_data(df)

    df_clean = df.copy()
    st.sidebar.header("🔍 Filters")
    clear = st.sidebar.button("Clear All Filters")

    # Setup filters
    common_names = sorted(df_clean['common_name'].unique())
    height_ranges = sorted(df_clean['height_range'].unique())
    min_diam_val = df_clean['diameter'].min(skipna=True)
    max_diam_val = df_clean['diameter'].max(skipna=True)
    min_year_val = df_clean['plant_year'].min(skipna=True)
    max_year_val = df_clean['plant_year'].max(skipna=True)

    min_diam = int(min_diam_val) if pd.notnull(min_diam_val) else 0
    max_diam = int(max_diam_val) if pd.notnull(max_diam_val) else 100
    min_year = int(min_year_val) if pd.notnull(min_year_val) else 2000
    max_year = int(max_year_val) if pd.notnull(max_year_val) else datetime.now().year

    selected_names = st.sidebar.multiselect("Tree Type", common_names) if not clear else []
    selected_heights = st.sidebar.multiselect("Height Range", height_ranges) if not clear else []
    min_diameter = st.sidebar.slider("Minimum Diameter", min_diam, max_diam, min_diam) if not clear else min_diam
    selected_year = st.sidebar.slider("Planted After Year", min_year, max_year, min_year) if not clear else min_year

    # Apply filters
    if selected_names or selected_heights or min_diameter > min_diam or selected_year > min_year:
        df_filtered = df[df['diameter'].notnull() & df['plant_year'].notnull()].copy()
        if selected_names:
            df_filtered = df_filtered[df_filtered['common_name'].isin(selected_names)]
        if selected_heights:
            df_filtered = df_filtered[df_filtered['height_range'].isin(selected_heights)]
        df_filtered = df_filtered[df_filtered['diameter'] >= min_diameter]
        df_filtered = df_filtered[df_filtered['plant_year'] >= selected_year]
    else:
        df_filtered = df

    st.subheader(f"🌲 Showing {len(df_filtered)} Trees in {selected}")
    if df_filtered.empty:
        st.info("No trees match the selected filters.")
    else:
        st_folium(create_map(df_filtered), width=700, height=500, key="filtered-map")

        st.markdown("### 📊 Statistics")
        avg_diameter = df_filtered['diameter'].mean()
        oldest = df_filtered['plant_year'].min()
        newest = df_filtered['plant_year'].max()

        k1, k2, k3 = st.columns(3)
        k1.metric("Average Diameter", f"{avg_diameter:.1f} in")
        k2.metric("Oldest Year", f"{int(oldest) if pd.notnull(oldest) else 'Unknown'}")
        k3.metric("Newest Year", f"{int(newest) if pd.notnull(newest) else 'Unknown'}")

        st.markdown("### Tree Distributions")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top Tree Types**")
            chart_data = df_filtered['common_name'].value_counts().nlargest(10).reset_index()
            chart_data.columns = ['Tree Type', 'Count']
            st.altair_chart(alt.Chart(chart_data).mark_bar(color=PRIMARY_COLOR).encode(
                x='Count:Q', y=alt.Y('Tree Type:N', sort='-x')), use_container_width=True)

        with col2:
            st.markdown("**Height Range Distribution**")
            height_data = df_filtered['height_range'].value_counts().reset_index()
            height_data.columns = ['Height Range', 'Count']
            st.altair_chart(alt.Chart(height_data).mark_bar(color=PRIMARY_COLOR).encode(
                x='Count:Q', y=alt.Y('Height Range:N', sort='-x')), use_container_width=True)

        st.markdown("### 📚 Tree Spotlight")
        spotlight = st.selectbox("Highlight a Tree", [""] + df_filtered['common_name'].unique().tolist())
        if spotlight:
            spotlight_df = df_filtered[df_filtered['common_name'] == spotlight]
            if not spotlight_df.empty:
                info = spotlight_df.iloc[0]
                wiki = info['species_name'].replace(" ", "_")
                st.markdown(f"**Common Name:** {spotlight}<br>**Latin Name:** *{info['species_name']}*<br>[Learn more on Wikipedia](https://en.wikipedia.org/wiki/{wiki})", unsafe_allow_html=True)
                st_folium(create_map(df_filtered, spotlight), width=700, height=500, key="spotlight-map")
