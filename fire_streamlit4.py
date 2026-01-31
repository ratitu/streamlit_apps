import streamlit as st
import ee
import folium
import geemap
from streamlit_folium import folium_static
from datetime import date

# 1. Configuração da página deve ser a primeira instrução
st.set_page_config(layout="wide", page_title="Monitoramento de Incêndios")

# 2. Inicialização do Earth Engine
try:
    ee.Initialize(project="ee-passeionamatamapas")
except Exception as e:
    ee.Authenticate()
    ee.Initialize(project="ee-passeionamatamapas")

st.title("🔥 Monitoramento de Severidade de Incêndios")

# --- BARRA LATERAL ---
st.sidebar.header("Configurações da Análise")
lat = st.sidebar.number_input("Latitude", value=-15.7938, format="%.4f")
lon = st.sidebar.number_input("Longitude", value=-47.8828, format="%.4f")

# Área de análise
point = ee.Geometry.Point([lon, lat]).buffer(5000).bounds()

col1, col2 = st.sidebar.columns(2)
pre_fire_start = col1.date_input("Início Pré-Fogo", date(2023, 5, 1))
pre_fire_end = col2.date_input("Fim Pré-Fogo", date(2023, 6, 1))
post_fire_start = col1.date_input("Início Pós-Fogo", date(2023, 9, 1))
post_fire_end = col2.date_input("Fim Pós-Fogo", date(2023, 10, 1))

def get_s2_collection(start, end, area):
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(area)
            .filterDate(str(start), str(end))
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))
    
    count = col.size().getInfo()
    if count == 0:
        return None
    return col.median().clip(area)

# --- BOTÃO ÚNICO DE PROCESSAMENTO ---
if st.sidebar.button("Gerar Análise Completa"):
    with st.spinner("Processando dados de satélite..."):
        # Coleta das imagens
        pre_image = get_s2_collection(pre_fire_start, pre_fire_end, point)
        post_image = get_s2_collection(post_fire_start, post_fire_end, point)

        if pre_image is None or post_image is None:
            st.error("Nenhuma imagem sem nuvens encontrada para os períodos selecionados.")
        else:
            # Cálculo do dNBR
            nbr_pre = pre_image.normalizedDifference(['B8', 'B12'])
            nbr_post = post_image.normalizedDifference(['B8', 'B12'])
            dnbr = nbr_pre.subtract(nbr_post)

            # Criar o Mapa com Geemap (Interface interativa)
            st.subheader("Visualização Interativa (Geemap)")
            Map = geemap.Map()
            Map.centerObject(point, 12)
            
            dnbr_viz = {
                'min': -0.1, 'max': 0.66, 
                'palette': ['#7a8737', '#acbe4d', '#0ae042', '#fff70b', '#ffaf38', '#ff641b', '#a41fd6']
            }

            Map.addLayer(pre_image, {'bands': ['B4', 'B3', 'B2'], 'max': 3000}, "Imagem Pré-Fogo")
            Map.addLayer(post_image, {'bands': ['B4', 'B3', 'B2'], 'max': 3000}, "Imagem Pós-Fogo")
            Map.addLayer(dnbr, dnbr_viz, "Severidade (dNBR)")
            Map.add_colorbar(dnbr_viz, label="Severidade dNBR")
            
            # Renderiza o mapa do geemap
            Map.to_streamlit(height=600)
            
            st.divider()
            
            # Criar o Mapa com Folium Estático (Se o geemap falhar, este é o backup)
            st.subheader("Mapa Estático (Folium)")
            m = folium.Map(location=[lat, lon], zoom_start=12)
            
            map_id_dict = ee.Image(dnbr).getMapId(dnbr_viz)
            
            folium.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name='Severidade dNBR',
                overlay=True,
                control=True
            ).add_to(m)
            
            folium_static(m)
            
            st.success(f"Análise concluída com sucesso!")
