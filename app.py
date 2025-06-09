import pandas as pd
import networkx as nx
import folium
from folium import PolyLine, Marker
from streamlit_folium import st_folium
import streamlit as st
from datetime import timedelta
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
import json
import os

# ---------- Setup ----------
st.set_page_config(layout="wide")
st.title("🛫 Summer Vacation 2025")

# ---------- Sample Data ----------
df = pd.read_excel('data/data.xlsx', sheet_name='Sheet1')
df = df[df['route_type'] == 'outbound']
df['flight_id'] = df.index.astype(str)
df["departure_datetime"] = pd.to_datetime(df["departure_date"].astype(str) + " " + df["departure_time"].astype(str))
df["arrival_datetime"] = pd.to_datetime(df["arrival_date"].astype(str) + " " + df["arrival_time"].astype(str))
df['price'] = pd.to_numeric(df['price'], errors='coerce')

CITY_COORDS = {
    "Bratislava": (48.1486, 17.1077),
    "Budapest": (47.4979, 19.0402),
    "Chelm": (51.1431, 23.4715),
    "Chop": (48.4265, 22.2033),
    "Katowice": (50.2649, 19.0238),
    "Krakow": (50.0647, 19.9450),
    "Kyiv": (50.4501, 30.5234),
    "Lublin": (51.2465, 22.5684),
    "Poznan": (52.4064, 16.9252),
    "Warsaw": (52.2297, 21.0122),
    "Wroclaw": (51.1079, 17.0385),
    "Chisinau": (47.0105, 28.8638),
}

# ---------- Geocoding ----------
# @st.cache_data(show_spinner=False)
# def get_coordinates(city):
#     geolocator = Nominatim(user_agent="flight-path-app")
#     try:
#         location = geolocator.geocode(city, timeout=10)
#         if location:
#             return (location.latitude, location.longitude)
#     except GeocoderTimedOut:
#         time.sleep(1)
#         return get_coordinates(city)
#     return None
def get_coordinates(city):
    return CITY_COORDS.get(city, (None, None))

def build_city_coordinates(df):
    coord_path = "data/city_coords.json"
    if os.path.exists(coord_path):
        with open(coord_path, "r", encoding="utf-8") as f:
            city_coords = json.load(f)
    else:
        city_coords = {}

    cities = pd.unique(df[['departure_city', 'arrival_city']].values.ravel())
    updated = False
    for city in cities:
        if city not in city_coords or city_coords[city] is None:
            coords = get_coordinates(city)
            if coords:
                city_coords[city] = coords
                updated = True
    if updated:
        with open(coord_path, "w", encoding="utf-8") as f:
            json.dump(city_coords, f)

    return city_coords

city_coords = build_city_coordinates(df)

# ---------- Graph Builder ----------
def build_graph(df, min_transfer, max_transfer):
    G = nx.DiGraph()
    for _, row in df.iterrows():
        G.add_node(row['flight_id'], **row.to_dict())
    for i, f1 in df.iterrows():
        for j, f2 in df.iterrows():
            if f1['arrival_city'] == f2['departure_city']:
                transfer = f2['departure_datetime'] - f1['arrival_datetime']
                if min_transfer <= transfer <= max_transfer:
                    G.add_edge(f1['flight_id'], f2['flight_id'])
    return G

# ---------- Path Finder ----------
def find_paths(df, G, start_city, end_city):
    paths = []
    starts = df[df['departure_city'] == start_city]['flight_id']
    ends = df[df['arrival_city'] == end_city]['flight_id']
    for s in starts:
        for e in ends:
            for path in nx.all_simple_paths(G, s, e):
                paths.append(path)
    return paths

# ---------- Render Map & Table ----------
def render_path(path_ids, G, city_coords):
    m = folium.Map(location=[47, 24], zoom_start=5, tiles="CartoDB positron")
    rows = []
    total_price = 0

    nodes = [G.nodes[fid] for fid in path_ids]
    transfer_times = [
        nodes[i + 1]['departure_datetime'] - nodes[i]['arrival_datetime']
        for i in range(len(nodes) - 1)
    ] + [""]

    for idx, node in enumerate(nodes):
        dep_city = node['departure_city']
        arr_city = node['arrival_city']
        dep_coords = city_coords.get(dep_city)
        arr_coords = city_coords.get(arr_city)

        if dep_coords:
            folium.Marker(
                dep_coords,
                tooltip=f"From: {dep_city}",
                icon=folium.Icon(color='blue', icon='plane-departure', prefix='fa')
            ).add_to(m)

        if arr_coords:
            folium.Marker(
                arr_coords,
                tooltip=f"To: {arr_city}",
                icon=folium.Icon(color='green', icon='plane-arrival', prefix='fa')
            ).add_to(m)

        if dep_coords and arr_coords:
            PolyLine(
                [dep_coords, arr_coords],
                color="blue", weight=3, opacity=0.8,
                tooltip=f"{node['price']} UAH"
            ).add_to(m)

        rows.append({
            "From": dep_city,
            "Departure": node['departure_datetime'],
            "Departure Place": node.get('departure_place', ''),
            "To": arr_city,
            "Arrival": node['arrival_datetime'],
            "Arrival Place": node.get('arrival_place', ''),
            "Transport": node.get('transport_type', ''),
            "Company": node.get('company', ''),
            "Price (UAH)": node['price'],
            "Transfer Time": transfer_times[idx]
        })

        total_price += node['price']

    df_table = pd.DataFrame(rows)
    total_row = {col: "" for col in df_table.columns}
    total_row["Price (UAH)"] = total_price
    df_table.loc[len(df_table.index)] = total_row
    return m, df_table

# ---------- Sidebar UI ----------
with st.sidebar:
    st.header("✈️ Route Settings")
    start_city = st.selectbox("From", sorted(df['departure_city'].unique()))
    end_city = st.selectbox("To", sorted(df['arrival_city'].unique()))
    min_t = st.number_input("Min transfer (min)", value=60, step=10)
    max_t = st.number_input("Max transfer (min)", value=800, step=10)

# ---------- Main Logic ----------
min_td = timedelta(minutes=min_t)
max_td = timedelta(minutes=max_t)
G = build_graph(df, min_td, max_td)
paths = find_paths(df, G, start_city, end_city)

if not paths:
    st.warning("No valid paths found for selected cities and transfer window.")
else:
    # Initialize index in session state
    if 'path_index' not in st.session_state:
        st.session_state.path_index = 0

    # Handle button clicks
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("◀️ Prev"):
            st.session_state.path_index = (st.session_state.path_index - 1) % len(paths)
    with col3:
        if st.button("Next ▶️"):
            st.session_state.path_index = (st.session_state.path_index + 1) % len(paths)

    idx = st.session_state.path_index

    m, df_table = render_path(paths[int(idx)], G, city_coords)

    st.subheader(f"Path {idx + 1} of {len(paths)}")
    st_folium(m, use_container_width=True, height=600)
    st.dataframe(df_table, use_container_width=True)