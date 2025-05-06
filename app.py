import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import time
from datetime import datetime
import pandas as pd
import altair as alt

# --- Dashboard Styles ---
st.set_page_config(page_title="Tree Dashboard", layout="wide")
PRIMARY_COLOR = "#A7C7E7"
DARK_COLOR = "#2C2C2C"

st.markdown(f"""
    <style>
    .stApp {{
        background-color: white;
        color: {DARK_COLOR};
    }}
    .block-container {{
        padding-top: 2rem;
    }}
    .stButton>button {{
        background-color: {PRIMARY_COLOR};
        color: black;
        border: none;
        border-radius: 5px;
        padding: 0.4rem 1rem;
        font-weight: 600;
    }}
    .stButton>button:hover {{
        background-color: #8bb2da;
        color: black;
    }}
    </style>
""", unsafe_allow_html=True)

# --- Data Fetching and Processing ---
@st.cache_data(ttl=3600)
def fetch_neighbourhood_tree_data(neighbourhood):
    base_url = "https://opendata.vancouver.ca"
    api_base_path = "/api/explore/v2.1/catalog/datasets"
    dataset_id = "public-trees"
    records_endpoint = f"{api_base_path}/{dataset_id}/records"
    all_results = []
    offset = 0
    limit = 100
    MAX_OFFSET = 10000  # Prevent 400 error

    neighbourhood = neighbourhood.upper()
    st.info(f"Fetching all tree data for {neighbourhood} in batches...")
    progress_bar = st.progress(0.0)

    total_count = None
    while offset < MAX_OFFSET:
        url = f"{base_url}{records_endpoint}?limit={limit}&offset={offset}&where=neighbourhood_name='{neighbourhood}'"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            results = data.get('results', [])
            all_results.extend(results)

            if total_count is None:
                total_count = data.get('total_count', 0)
                if total_count == 0:
                    st.info(f"No tree records found for {neighbourhood}.")
                    break

            if len(results) == 0 or len(all_results) >= total_count:
                st.success(f"Fetched {len(all_results)} tree records for {neighbourhood}.")
                break

            offset += limit
            progress_bar.progress(min(1.0, offset / total_count))
            time.sleep(0.1)

        except Exception as e:
            st.error(f"Error: {e}")
            break

    progress_bar.empty()

    if offset >= MAX_OFFSET:
        st.warning("⚠️ API limit reached: only the first 10,000 tree records are shown.")

    return all_results

@st.cache_data(ttl=3600)
def process_tree_data(trees_data):
    processed = []
    for tree in trees_data:
        try:
            geometry = tree.get('geom', {}).get('geometry')
            if geometry and geometry.get('type') == 'Point':
                coords = geometry.get('coordinates', [None, None])
                if None in coords:
                    continue
                processed.append({
                    'latitude': coords[1],
                    'longitude': coords[0],
                    'common_name': tree.get('common_name') or 'Unknown',
                    'species_name': tree.get('species_name') or 'Unknown',
                    'height_range': tree.get('height_range') or 'Unknown',
                    'diameter': pd.to_numeric(tree.get('diameter'), errors='coerce'),
                    'plant_date': tree.get('date_planted'),
                    'neighbourhood': tree.get('neighbourhood_name') or 'Unknown'
                })
        except Exception as e:
            st.warning(f"Error processing tree: {e}")
    return pd.DataFrame(processed)

def create_tree_map(trees, center, zoom, highlight_species=None):
    m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB Positron")
    for _, tree in trees.iterrows():
        is_highlighted = highlight_species and tree['common_name'] == highlight_species
        color = PRIMARY_COLOR if is_highlighted else 'green'
        fill_opacity = 0.9 if is_highlighted else 0.5
        tooltip = f"<b>{tree['common_name']}</b><br>Species: {tree['species_name']}<br>Planted: {tree['plant_date'] or 'Unknown'}"
        folium.CircleMarker(
            location=[tree['latitude'], tree['longitude']],
            radius=6 if is_highlighted else 4,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=fill_opacity,
            tooltip=tooltip
        ).add_to(m)
    return m

def filters_active(selected_names, selected_heights, min_diameter, selected_year, min_year):
    return (
        selected_names or
        selected_heights or
        min_diameter > 0 or
        selected_year > min_year
    )

# --- App Main ---
def main():
    st.title("🌳 Vancouver Trees")

    neighbourhoods = [
        "", "ARBUTUS RIDGE", "DOWNTOWN", "DUNBAR-SOUTHLANDS", "FAIRVIEW",
        "GRANDVIEW-WOODLAND", "HASTINGS-SUNRISE", "KENSINGTON-CEDAR COTTAGE",
        "KERRISDALE", "KILLARNEY", "KITSILANO", "MARPOLE", "MOUNT PLEASANT",
        "OAKRIDGE", "RENFREW-COLLINGWOOD", "RILEY PARK", "SHAUGHNESSY",
        "SOUTH CAMBIE", "STRATHCONA", "SUNSET", "VICTORIA-FRASERVIEW",
        "WEST END", "WEST POINT GREY"
    ]

    selected = st.selectbox("Select Neighbourhood", neighbourhoods)

    if not selected:
        st.info("Please select a neighbourhood to begin.")
        return

    if 'last_neighbourhood' not in st.session_state or st.session_state.last_neighbourhood != selected:
        st.session_state.last_neighbourhood = selected
        raw_data = fetch_neighbourhood_tree_data(selected)
        st.session_state.trees_df = process_tree_data(raw_data)

    df = st.session_state.trees_df.copy()
    df['common_name'] = df['common_name'].str.upper().str.strip()
    df['plant_year'] = pd.to_datetime(df['plant_date'], errors='coerce').dt.year
    df['diameter'] = df['diameter'].fillna(0)

    with st.sidebar:
        st.header("🔍 Filters")
        min_year = int(df['plant_year'].min(skipna=True) or 2000)
        max_year = int(df['plant_year'].max(skipna=True) or datetime.now().year)

        clear = st.button("Clear All Filters")
        if clear:
            st.session_state['selected_names'] = []
            st.session_state['selected_heights'] = []
            st.session_state['min_diameter'] = 0
            st.session_state['selected_year'] = min_year

        selected_names = st.multiselect("Tree Type", sorted(df['common_name'].dropna().unique()), key="selected_names")
        min_diameter = st.slider("Minimum Diameter (cm)", 0, int(df['diameter'].max()), 0, key="min_diameter")
        selected_heights = st.multiselect("Height Range", sorted(df['height_range'].dropna().unique()), key="selected_heights")
        selected_year = st.slider("Planted After Year", min_year, max_year, min_year, key="selected_year")

    # Apply filters only if actively used
    if filters_active(selected_names, selected_heights, min_diameter, selected_year, min_year):
        filtered_df = df.copy()
        if selected_names:
            filtered_df = filtered_df[filtered_df['common_name'].isin(selected_names)]
        if selected_heights:
            filtered_df = filtered_df[filtered_df['height_range'].isin(selected_heights)]
        filtered_df = filtered_df[filtered_df['diameter'] >= min_diameter]
        filtered_df = filtered_df[filtered_df['plant_year'].fillna(0).astype(int) >= selected_year]
    else:
        filtered_df = df.copy()

    st.subheader(f"🌲 Showing {len(filtered_df)} Trees in {selected}")

    if not filtered_df.empty:
        center_lat = filtered_df['latitude'].mean()
        center_lon = filtered_df['longitude'].mean()

        # Initial map (no spotlight)
        m = create_tree_map(filtered_df, [center_lat, center_lon], 14)
        st_folium(m, width=700, height=500)

        st.markdown("### 📊 Tree Statistics")
        avg_diameter = filtered_df['diameter'].mean()
        oldest_year = filtered_df['plant_year'].min()
        newest_year = filtered_df['plant_year'].max()

        k1, k2, k3 = st.columns(3)
        k1.metric("Average Diameter (cm)", f"{avg_diameter:.1f}")
        k2.metric("Oldest Tree Planted", f"{int(oldest_year) if pd.notnull(oldest_year) else 'Unknown'}")
        k3.metric("Most Recently Planted", f"{int(newest_year) if pd.notnull(newest_year) else 'Unknown'}")

        tree_counts = filtered_df['common_name'].value_counts().nlargest(10).reset_index()
        tree_counts.columns = ['Tree Type', 'Count']
        chart1 = alt.Chart(tree_counts).mark_bar(color=PRIMARY_COLOR).encode(
            x=alt.X('Count:Q', title='Tree Count'),
            y=alt.Y('Tree Type:N', sort='-x', title='Tree Type')
        ).properties(title='Top 10 Tree Types')

        height_counts = filtered_df['height_range'].value_counts().reset_index()
        height_counts.columns = ['Height Range', 'Count']
        chart2 = alt.Chart(height_counts).mark_bar(color=PRIMARY_COLOR).encode(
            x=alt.X('Count:Q', title='Tree Count'),
            y=alt.Y('Height Range:N', sort='-x', title='Height Range')
        ).properties(title='Height Range Distribution')

        col1, col2 = st.columns(2)
        col1.altair_chart(chart1, use_container_width=True)
        col2.altair_chart(chart2, use_container_width=True)

        # --- Tree Spotlight at the Bottom ---
        st.markdown("---")
        st.markdown("### 📚 Tree Spotlight")

        edu_trees = sorted(filtered_df['common_name'].dropna().unique())
        highlighted_species = st.selectbox("Highlight a Tree (optional)", [""] + edu_trees)

        if highlighted_species:
            latin_name = filtered_df[filtered_df['common_name'] == highlighted_species]['species_name'].iloc[0]
            wiki_url = f"https://en.wikipedia.org/wiki/{latin_name.replace(' ', '_')}"
            st.markdown(f"""
                **Common Name:** {highlighted_species}  
                **Latin Name:** *{latin_name}*  
                [Learn more on Wikipedia]({wiki_url})
            """)
            # Redraw map with spotlight
            m = create_tree_map(filtered_df, [center_lat, center_lon], 14, highlight_species=highlighted_species)
            st_folium(m, width=700, height=500)

if __name__ == "__main__":
    main()
