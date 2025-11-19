import streamlit as st
import geopandas as gpd
import folium
from folium.plugins import MiniMap
import pandas as pd
from streamlit_folium import st_folium

st.set_page_config(page_title="Landorix – Pinal County", layout="wide")
st.title("Landorix – Unincorporated Pinal County")
st.markdown("**Vacant land ready for subdivision** — 100% current Pinal County zoning rules")

# 100% accurate zoning from your PDF (corrected)
ZONING_MIN_ACRES = {
    "SR": 3.3, "TR": 0.23, "GR": 1.25, "MR": 0.16, "MHS": 0.16, "RV": 1.0,
    "CR1": 0.46, "CR2": 0.92, "CR3": 0.23, "CR4": 0.41, "CR5": 0.16,
    "PAD": None
}

@st.cache_data(ttl=3600)
def get_leads():
    parcels = gpd.read_file("https://maps.pinal.gov/arcgis/rest/services/OpenData/Parcels/MapServer/0/query?where=1=1&outFields=*&f=geojson&resultRecordCount=50000")
    cities = gpd.read_file("https://maps.pinal.gov/arcgis/rest/services/Boundaries/Municipal_Boundaries/MapServer/0/query?where=1=1&outFields=*&f=geojson")
    parcels = parcels[~parcels.intersects(cities.unary_union)]
    
    parcels['acres'] = pd.to_numeric(parcels.get('ACRES', parcels.get('GIS_ACRES', 0)), errors='coerce').fillna(0)
    parcels['impval'] = pd.to_numeric(parcels.get('IMP_VALUE', 0), errors='coerce').fillna(0)
    parcels['zoning'] = parcels.get('ZONE', parcels.get('ZONING', '')).astype(str).str.upper().str.replace(r'[^A-Z0-9]','',regex=True)
    parcels['vacant'] = parcels['impval'] < 5000
    
    def rate(row):
        min_ac = ZONING_MIN_ACRES.get(row['zoning'])
        if not min_ac: return "Unknown zoning"
        a = row['acres']
        if a >= min_ac*4: return "VERY HIGH – 4-lot minor division"
        if a >= min_ac*2: return "HIGH – 2–3 lots"
        if a >= min_ac*1.1: return "MEDIUM – 1 split"
        return "LOW"
    
    parcels['potential'] = parcels.apply(rate, axis=1)
    return parcels[(parcels['vacant']) & (parcels['acres']>0.5) & parcels['potential'].str.contains('HIGH|VERY|MEDIUM')]

if st.button("Run Live Scan – Show Me the Money", type="primary", use_container_width=True):
    with st.spinner("Pulling fresh Pinal County data..."):
        leads = get_leads()
    st.success(f"Found {len(leads):,} subdivision-ready parcels!")
    
    m = folium.Map(location=[32.8, -111.3], zoom_start=9, tiles="CartoDB positron")
    for _, r in leads.iterrows():
        color = "darkred" if "VERY HIGH" in r['potential'] else "orange" if "HIGH" in r['potential'] else "green"
        folium.CircleMarker(
            location=[r.geometry.centroid.y, r.geometry.centroid.x],
            radius=max(6, r['acres']),
            color=color,
            popup=f"<b>{r['potential']}</b><br>{r['acres']:.1f} acres<br>APN: {r.get('PARCEL_ID','')}",
            fill=True
        ).add_to(m)
    MiniMap().add_to(m)
    st_folium(m, width=1200, height=700)
    
    csv = leads[['PARCEL_ID','OWNER_NAME','SITUS_ADDR','acres','ZONE','potential']].to_csv(index=False)
    st.download_button("Download All Leads (CSV/Excel)", csv, "landorix_pinal_leads.csv")

st.caption("Click the button any time for fresh data — works on phone too")
