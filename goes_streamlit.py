import streamlit as st
import ee
import geemap
from datetime import date, datetime, time, timedelta
import tempfile
import os
import json

st.set_page_config(layout="wide")
st.title("GOES Fire Timelapse App")

# Initialize Earth Engine
# On Streamlit Cloud we cannot run interactive OAuth. Use a service account stored in st.secrets.
def initialize_ee():
    # Expect these secrets to be set on Streamlit Cloud:
    # - GEE_SERVICE_ACCOUNT : service-account-email@PROJECT.iam.gserviceaccount.com
    # - GEE_PRIVATE_KEY : the full JSON key contents (the private key file) as a multiline string
    # - (optional) GEE_PROJECT : GCP project id (defaults to ee-passeionamatamapas)
    project = st.secrets.get("GEE_PROJECT", "ee-passeionamatamapas")

    if "GEE_SERVICE_ACCOUNT" in st.secrets and "GEE_PRIVATE_KEY" in st.secrets:
        sa_email = st.secrets["GEE_SERVICE_ACCOUNT"]
        sa_key_json = st.secrets["GEE_PRIVATE_KEY"]

        # Write the JSON key to a temporary file (EE expects a file path)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(sa_key_json)
        tmp.flush()
        tmp.close()
        key_path = tmp.name

        try:
            creds = ee.ServiceAccountCredentials(sa_email, key_path)
            ee.Initialize(credentials=creds, project=project)
            # remove key file after initialization for safety
            try:
                os.remove(key_path)
            except Exception:
                pass
            return True
        except Exception as e:
            st.error(f"Failed to initialize Earth Engine with service account: {e}")
            # keep the key file for debugging if needed; optionally remove it
            return False
    else:
        # Local / development fallback to interactive auth (allows local testing)
        try:
            ee.Initialize(project=project)
            return True
        except Exception:
            st.warning("Interactive Earth Engine authentication is required locally. You can also set a service account in Streamlit secrets for cloud runs.")
            try:
                ee.Authenticate()
                ee.Initialize(project=project)
                return True
            except Exception as e:
                st.error(f"Earth Engine authentication failed: {e}")
                return False

if not initialize_ee():
    st.stop()

# Define the region for South America
region = ee.Geometry.BBox(-85.0, -56.0, -34.0, 13.0)

# --- Date and Time Selection ---
st.subheader("1. Select Time Range")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Start Period**")
    start_d = st.date_input("Start date", date.today() - timedelta(days=1))
    start_t = st.time_input("Start time", time(0, 0)) # Defaults to midnight

with col2:
    st.markdown("**End Period**")
    end_d = st.date_input("End date", date.today())
    end_t = st.time_input("End time", time(23, 59)) # Defaults to end of day

# Combine date and time into the format geemap expects: 'YYYY-MM-DDTHH:mm'
start_date_str = datetime.combine(start_d, start_t).strftime('%Y-%m-%dT%H:%M')
end_date_str = datetime.combine(end_d, end_t).strftime('%Y-%m-%dT%H:%M')

# --- Generate Timelapse ---
if st.button('Generate Timelapse GIF'):
    if datetime.combine(start_d, start_t) >= datetime.combine(end_d, end_t):
        st.error("Error: End time must be after start time.")
    else:
        with st.spinner(f'Generating timelapse from {start_date_str} to {end_date_str}...'):
            with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp_gif_file:
                output_gif_path = tmp_gif_file.name

            try:
                timelapse_result = geemap.goes_fire_timelapse(
                    roi=region,
                    out_gif=output_gif_path,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    data='GOES-19',
                    scan='full_disk',
                    dimensions=600,
                    framesPerSecond=6,
                    date_format='YYYY-MM-dd HH:mm',
                    add_progress_bar=False,
                    mp4=False
                )

                st.session_state['generated_gif_path'] = output_gif_path
                st.success('Timelapse generated!')
                st.rerun() # Updated from experimental_rerun()

            except Exception as e:
                st.error(f"Error generating timelapse: {e}")
                if os.path.exists(output_gif_path):
                    os.remove(output_gif_path)

# --- Display Result ---
if 'generated_gif_path' in st.session_state and os.path.exists(st.session_state['generated_gif_path']):
    st.divider()
    st.subheader('Generated Timelapse GIF')
    st.image(st.session_state['generated_gif_path'], use_container_width=True)

    with open(st.session_state['generated_gif_path'], 'rb') as f:
        st.download_button(
            label="Download GIF",
            data=f,
            file_name=f"goes_fire_{start_date_str}.gif",
            mime="image/gif"
        )
