import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import io
import csv

# Set up the Streamlit page
st.set_page_config(page_title="Overall Project Score Dashboard", layout="wide")
st.title("🏆 Website Performance & Project Health Dashboard")
st.subheader("Compare the Last 3 Months against the Current 3 Months to calculate an Overall Health Score")

st.markdown("---")

def robust_read_csv(file_buffer):
    """Reads a CSV line-by-line, bypassing metadata rows dynamically."""
    content = file_buffer.read()
    if isinstance(content, bytes):
        text_content = content.decode('utf-8', errors='ignore')
    else:
        text_content = content
        
    lines = text_content.splitlines()
    reader = csv.reader(lines)
    all_rows = [row for row in reader if row]
    
    if not all_rows:
        return pd.DataFrame()
        
    max_cols = max(len(row) for row in all_rows)
    valid_rows = [row for row in all_rows if len(row) == max_cols]
    
    if not valid_rows:
        return pd.DataFrame()
        
    df = pd.DataFrame(valid_rows[1:], columns=valid_rows[0])
    return df

def get_metric_sum(df, target_names):
    """Safely extracts the total sum of a dynamic metric from a dataframe."""
    for name in target_names:
        matched_col = [c for c in df.columns if name.lower() in c.lower()]
        if matched_col:
            # Clean values
            series = df[matched_col[0]].astype(str).str.replace(',', '').str.replace('%', '')
            return pd.to_numeric(series, errors='coerce').fillna(0).sum()
    return 0

# Sidebar configuration
st.sidebar.header("📁 Step 1: Upload Baseline (Previous 3 Months)")
gsc_zip_prev = st.sidebar.file_uploader("GSC Previous 3M (ZIP)", type=["zip"], key="gsc_prev")
ga_csv_prev = st.sidebar.file_uploader("GA Previous 3M (CSV)", type=["csv"], key="ga_prev")

st.sidebar.markdown("---")

st.sidebar.header("📁 Step 2: Upload Current (Recent 3 Months)")
gsc_zip_curr = st.sidebar.file_uploader("GSC Current 3M (ZIP)", type=["zip"], key="gsc_curr")
ga_csv_curr = st.sidebar.file_uploader("GA Current 3M (CSV)", type=["csv"], key="ga_curr")

st.sidebar.markdown("---")
gsc_report_type = st.sidebar.selectbox(
    "Internal GSC File Name Target:",
    ["Pages.csv", "Dates.csv", "Queries.csv"],
    index=0
)

def extract_gsc_df(zip_file, report_name):
    if zip_file is None: return None
    with zipfile.ZipFile(zip_file) as z:
        file_list = z.namelist()
        matched = [f for f in file_list if report_name.lower() in f.lower()]
        if matched:
            with z.open(matched[0]) as f: return robust_read_csv(f)
        else:
            csv_files = [f for f in file_list if f.endswith('.csv') and not f.startswith('__MACOSX')]
            if csv_files:
                with z.open(csv_files[0]) as f: return robust_read_csv(f)
    return None

# Check readiness
if gsc_zip_prev and ga_csv_prev and gsc_zip_curr and ga_csv_curr:
    try:
        # Load all 4 data frames
        df_gsc_prev = extract_gsc_df(gsc_zip_prev, gsc_report_type)
        df_gsc_curr = extract_gsc_df(gsc_zip_curr, gsc_report_type)
        df_ga_prev = robust_read_csv(ga_csv_prev)
        df_ga_curr = robust_read_csv(ga_csv_curr)
        
        # Aggregate Primary Metrics
        prev_clicks = get_metric_sum(df_gsc_prev, ['clicks'])
        curr_clicks = get_metric_sum(df_gsc_curr, ['clicks'])
        
        prev_impr = get_metric_sum(df_gsc_prev, ['impressions'])
        curr_impr = get_metric_sum(df_gsc_curr, ['impressions'])
        
        prev_sessions = get_metric_sum(df_ga_prev, ['sessions', 'visits'])
        curr_sessions = get_metric_sum(df_ga_curr, ['sessions', 'visits'])
        
        prev_conv = get_metric_sum(df_ga_prev, ['conversions', 'transactions'])
        curr_conv = get_metric_sum(df_ga_curr, ['conversions', 'transactions'])

        # Calculate Growth Deltas
        def calc_growth(curr, prev):
            if prev <= 0: return 0.0
            return ((curr - prev) / prev) * 100

        impr_growth = calc_growth(curr_impr, prev_impr)
        sessions_growth = calc_growth(curr_sessions, prev_sessions)
        clicks_growth = calc_growth(curr_clicks, prev_clicks)
        
        # --- HEALTH SCORING ENGINE ---
        # Baseline score starts at 70 (neutral performance marker).
        # Positive growth adds points; negative elements subtract points.
        score_component_1 = min(max(impr_growth * 0.35, -20), 15)
        score_component_2 = min(max(sessions_growth * 0.35, -20), 15)
        score_component_3 = min(max(clicks_growth * 0.30, -20), 10)
        
        final_score = int(70 + score_component_1 + score_component_2 + score_component_3)
        final_score = min(max(final_score, 0), 100) # Lock between 0 and 100
        
        # Score Callout Design
        st.markdown("---")
        st.subheader("🎯 Overall Project Score Evaluation")
        
        score_col1, score_col2 = st.columns([1, 2])
        
        with score_col1:
            if final_score >= 80:
                st.balloons()
                st.success(f"## **{final_score} / 100** \n\n 🔥 **Excellent Growth!** Your structural adjustments are driving strong performance metrics.")
            elif final_score >= 60:
                st.info(f"## **{final_score} / 100** \n\n 📈 **Steady Progress.** The project is stable with selective positive shifts across key metrics.")
            else:
                st.warning(f"## **{final_score} / 100** \n\n ⚠️ **Performance Decline.** Action recommended. Primary channels are lagging behind your baseline period.")
                
        with score_col2:
            # Gauge / Summary Bar Chart representation
            score_data = pd.DataFrame({
                'Metric Group': ['Visibility (Impr.)', 'Acquisition (Sessions)', 'Conversion (Clicks)'],
                'Growth Shift %': [impr_growth, sessions_growth, clicks_growth]
            })
            fig_score = px.bar(
                score_data, x='Growth Shift %', y='Metric Group', orientation='h', 
                text_auto='.1f', color='Growth Shift %',
                color_continuous_scale=px.colors.diverging.RdYlGn,
                title="Performance Shifts Between 3-Month Blocks"
            )
            st.plotly_chart(fig_score, use_container_width=True)

        st.markdown("---")
        
        # --- SIDE BY SIDE PERFORMANCE SHEET ---
        st.subheader("📊 Primary Key Metric Comparison Table")
        
        summary_grid = pd.DataFrame({
            'Performance Indicator': ['GSC Search Impressions', 'GA Website Sessions', 'GSC Organic Clicks', 'GA Target Conversions'],
            'Previous 3 Months': [f"{int(prev_impr):,}", f"{int(prev_sessions):,}", f"{int(prev_clicks):,}", f"{int(prev_conv):,}"],
            'Current 3 Months': [f"{int(curr_impr):,}", f"{int(curr_sessions):,}", f"{int(curr_clicks):,}", f"{int(curr_conv):,}"],
            'Growth Delta %': [f"{impr_growth:+.2f}%", f"{sessions_growth:+.2f}%", f"{clicks_growth:+.2f}%", f"{calc_growth(curr_conv, prev_conv):+.2f}%"]
        })
        st.table(summary_grid)

    except Exception as e:
        st.error(f"An processing mismatch occurred: {e}")
else:
    st.info("💡 **Ready to score your performance?** Please upload your previous 3-Month structural baseline files followed by your current 3-Month tracking data in the sidebar configuration layout.")
