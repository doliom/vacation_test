import pandas as pd
import networkx as nx
import streamlit as st
from datetime import timedelta

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

# ---------- Table Renderer ----------
def render_path_table(path_ids, G):
    rows = []
    total_price = 0

    nodes = [G.nodes[fid] for fid in path_ids]
    transfer_times = [
        nodes[i + 1]['departure_datetime'] - nodes[i]['arrival_datetime']
        for i in range(len(nodes) - 1)
    ] + [""]

    for idx, node in enumerate(nodes):
        rows.append({
            "From": node['departure_city'],
            "Departure": node['departure_datetime'],
            "Departure Place": node.get('departure_place', ''),
            "To": node['arrival_city'],
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
    return df_table

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
    if 'path_index' not in st.session_state:
        st.session_state.path_index = 0

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("◀️ Prev"):
            st.session_state.path_index = (st.session_state.path_index - 1) % len(paths)
    with col3:
        if st.button("Next ▶️"):
            st.session_state.path_index = (st.session_state.path_index + 1) % len(paths)

    idx = st.session_state.path_index
    df_table = render_path_table(paths[int(idx)], G)

    st.subheader(f"Path {idx + 1} of {len(paths)}")
    st.dataframe(df_table, use_container_width=True)
