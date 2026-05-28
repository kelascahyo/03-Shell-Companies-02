import streamlit as st
import pandas as pd
import networkx as nx
import json
import os

# Konfigurasi halaman utama Streamlit (Wide Layout)
st.set_page_config(
    page_title="Corporate Shell & Tax Leakage Network Intelligence",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Perbaikan Error: Kustomisasi CSS dibersihkan dari indentasi tab agar tidak merusak parser Markdown Streamlit
st.markdown("<style>.reportview-container { background: #0e1117; } .main .block-container { padding-top: 2rem; } h1, h2, h3 { color: #ffffff; font-family: 'Segoe UI', sans-serif; } .metric-card { background-color: #1a1c24; border: 1px solid #464855; border-radius: 8px; padding: 15px; margin-bottom: 10px; } .metric-title { font-size: 13px; color: #a3a8b4; text-transform: uppercase; letter-spacing: 0.5px; } .metric-value { font-size: 24px; font-weight: bold; color: #ff4b4b; margin-top: 5px; }</style>", unsafe_allowed_html=True)

# Narasi analisis dalam Bahasa Inggris
st.title("🛡️ Anti-Tax Avoidance & Shell Company Network Analyzer")
st.markdown("""
### Executive Brief & System Overview
This analytics workspace is purpose-built to map corporate structures, identify cross-border profit shifting, and flag **Shell Companies** or high-risk unregistered entities. Entities designated as **LN (Luar Negeri / Foreign)** or **Non NPWP (No Tax Registration Number)** represent strategic transfer-pricing risk surfaces where outbound capital, dividends, or ownership values can be obfuscated to achieve aggressive tax optimization or tax evasion.

**Analytic Focus:** Detecting Indonesian domestic corporate entities (`Badan`) that redirect substantial dividend streams or transfer heavy equity percentages into high-risk foreign jurisdictions or unregistered structures.
""")

# Fungsi memuat data dengan cache otomatis
@st.cache_data
def load_network_data():
    if os.path.exists("nodes_masked.csv") and os.path.exists("edges_masked_part1_a.csv"):
        nodes = pd.read_csv("nodes_masked.csv")
        edges = pd.read_csv("edges_masked_part1_a.csv")
        return nodes, edges
    else:
        st.error("Error: 'nodes_masked.csv' atau 'edges_masked_part1_a.csv' tidak ditemukan di root folder!")
        return pd.DataFrame(), pd.DataFrame()

nodes_df, edges_df = load_network_data()

if not nodes_df.empty and not edges_df.empty:
    # Pra-pemrosesan teks kelompok jenis node
    nodes_df['jenis_node'] = nodes_df['jenis_node'].str.strip()
    
    # Mapping untuk mempercepat pencarian data relasi di grafik
    node_name_map = dict(zip(nodes_df['id'], nodes_df['nama']))
    node_type_map = dict(zip(nodes_df['id'], nodes_df['jenis_node']))
    
    # Definisi kelompok berisiko tinggi
    high_risk_types = ['LN', 'Non NPWP']
    high_risk_nodes = set(nodes_df[nodes_df['jenis_node'].isin(high_risk_types)]['id'])
    
    # Tandai relasi yang mengalir menuju objek berisiko tinggi
    edges_df['is_to_high_risk'] = edges_df['target'].isin(high_risk_nodes)
    
    # Hitung total akumulasi pengiriman dividen outbound
    outbound_div = edges_df[edges_df['is_to_high_risk']].groupby('sumber')['dividen'].sum().to_dict()
    nodes_df['total_dividen_outbound'] = nodes_df['id'].map(outbound_div).fillna(0)

    # Panel Kontrol Interaktif di Sidebar sebelah kiri
    st.sidebar.header("🔍 Dynamic Network Filtering")
    
    analysis_mode = st.sidebar.radio(
        "Select Scope View:",
        ["High-Risk Cross-Border Network Only", "Full Taxpayer Ecosystem Network"]
    )
    
    min_dividend = st.sidebar.number_input(
        "Minimum Outbound Dividend Stream (Rp):", 
        min_value=0, value=0, step=100000000
    )
    
    min_percentage = st.sidebar.slider(
        "Minimum Equity Share Percentage (%):",
        0.0, 100.0, 0.0
    )

    # Proses Filtering Data menggunakan Pandas
    filtered_edges = edges_df.copy()
    
    if analysis_mode == "High-Risk Cross-Border Network Only":
        filtered_edges = filtered_edges[
            filtered_edges['sumber'].isin(high_risk_nodes) | 
            filtered_edges['target'].isin(high_risk_nodes)
        ]
        
    filtered_edges = filtered_edges[
        (filtered_edges['dividen'] >= min_dividend) & 
        (filtered_edges['persentase'] >= min_percentage)
    ]
    
    active_node_ids = set(filtered_edges['sumber'].unique()).union(set(filtered_edges['target'].unique()))
    filtered_nodes = nodes_df[nodes_df['id'].isin(active_node_ids)]

    # Perhitungan Metrik Ringkasan Eksekutif (KPI Card)
    total_leakage = filtered_edges[filtered_edges['is_to_high_risk']]['dividen'].sum()
    high_risk_count = filtered_nodes[filtered_nodes['jenis_node'].isin(high_risk_types)]['id'].nunique()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-title">🚨 Total Flagged Outbound Dividends</div><div class="metric-value">Rp {total_leakage:,.2f}</div></div>', unsafe_allowed_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-title">🏢 High-Risk Shell Nodes (LN & Non-NPWP)</div><div class="metric-value">{high_risk_count} Entities</div></div>', unsafe_allowed_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-title">🔗 Total Active Network Ties</div><div class="metric-value">{len(filtered_edges)} Links</div></div>', unsafe_allowed_html=True)

    # Transformasikan objek data ke dalam representasi standar format JSON Node-Link untuk D3.js
    d3_nodes = []
    for _, row in filtered_nodes.iterrows():
        d3_nodes.append({
            "id": int(row['id']),
            "nama": row['nama'],
            "jenis_node": row['jenis_node'],
            "total_dividen_outbound": float(row['total_dividen_outbound'])
        })
        
    d3_links = []
    for _, row in filtered_edges.iterrows():
        s_id = int(row['sumber'])
        t_id = int(row['target'])
        d3_links.append({
            "source": s_id,
            "target": t_id,
            "source_name": node_name_map.get(s_id, "Unknown"),
            "target_name": node_name_map.get(t_id, "Unknown"),
            "source_type": node_type_map.get(s_id, "Unknown"),
            "target_type": node_type_map.get(t_id, "Unknown"),
            "persentase": float(row['persentase']),
            "nilai": float(row['nilai']),
            "dividen": float(row['dividen']),
            "high_risk_connection": bool(row['is_to_high_risk'])
        })
        
    graph_payload = {"nodes": d3_nodes, "links": d3_links}

    # Merender lapisan visualisasi grafik interaktif D3 ke dalam Streamlit
    st.subheader("🕸️ Interactive Relational Graph Layer (D3.js Force Simulation)")
    st.info("💡 Interaction Tip: Drag nodes to rearrange. Hover over nodes or connection vectors to drill-down into detailed tax transaction attributes & dividend paths.")

    # Membaca template HTML komponen D3
    with open("components/d3_network.html", "r") as html_f:
        html_template = html_f.read()
        
    # Injeksi payload JSON langsung ke dalam window scope iframe D3 secara aman
    injected_html = html_template.replace(
        "// Run immediately if embedded directly with data injected into window payload",
        f"window.graphDataPayload = {json.dumps(graph_payload)};"
    )
    
    # Tampilkan grafik menggunakan modul HTML Iframe bawaan Streamlit
    st.components.v1.html(injected_html, height=650, scrolling=False)

    # Tabel Data Forensik Audit Perpajakan
    st.subheader("📊 High-Risk Outbound Transfer Transaction Logs")
    risk_table = filtered_edges[filtered_edges['is_to_high_risk']].copy()
    if not risk_table.empty:
        risk_table['Source Corporate'] = risk_table['sumber'].map(node_name_map)
        risk_table['Target Risk Entity'] = risk_table['target'].map(node_name_map)
        risk_table['Target Type'] = risk_table['target'].map(node_type_map)
        
        display_cols = ['Source Corporate', 'Target Risk Entity', 'Target Type', 'persentase', 'nilai', 'dividen']
        formatted_table = risk_table[display_cols].rename(columns={
            'persentase': 'Share Ownership %',
            'nilai': 'Shares Capital (IDR)',
            'dividen': 'Dividends Paid (IDR)'
        }).sort_values(by='Dividends Paid (IDR)', ascending=False)
        
        st.dataframe(formatted_table, use_container_width=True)
    else:
        st.write("No transaction metrics match the current high-risk filter thresholds.")
else:
    st.warning("Please verify data source availability.")
