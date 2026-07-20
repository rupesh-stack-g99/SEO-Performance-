import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import io
import csv

st.set_page_config(page_title="Deep Project Score Dashboard", layout="wide")
st.title("🏆 Comprehensive Project Health & Scoring Suite")
st.subheader("Deep multi-metric comparative analytics using native GSC & GA4 period exports")

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

def clean_and_sum(df, col_name):
    """Safely converts a target metric column to numerical format and aggregates."""
    if col_name in df.columns:
        series = df[col_name].astype(str).str.replace(',', '').str.replace('%', '')
        return pd.to_numeric(series, errors='coerce').fillna(0).sum()
    return 0

def clean_and_mean(df, col_name):
    """Safely converts a column to numerical format and returns the average (ideal for Position/CTR)."""
    if col_name in df.columns:
        series = df[col_name].astype(str).str.replace(',', '').str.replace('%', '')
        valid_series = pd.to_numeric(series, errors='coerce').dropna()
        return valid_series.mean() if not valid_series.empty else 0
    return 0

# Sidebar setup for custom thresholds
st.sidebar.header("📁 Step 1: Upload Comparison Reports")
gsc_file = st.sidebar.file_uploader("1. GSC Comparison Export (ZIP/CSV)", type=["zip", "csv"])
ga_file = st.sidebar.file_uploader("2. GA4 Comparison Export (CSV)", type=["csv"])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Scoring Framework Weights")
st.sidebar.caption("Adjust weighting priorities based on current project goals")
w_vis = st.sidebar.slider("Visibility Weight (Impressions/Position)", 0.0, 1.0, 0.25, 0.05)
w_acq = st.sidebar.slider("Acquisition Weight (Clicks/Sessions)", 0.0, 1.0, 0.45, 0.05)
w_eng = st.sidebar.slider("Conversion/Engagement Weight", 0.0, 1.0, 0.30, 0.05)

# Validate manual weighting bounds
if round(w_vis + w_acq + w_eng, 2) != 1.00:
    st.sidebar.warning(f"⚠️ Weights total {round(w_vis + w_acq + w_eng, 2)}. Adjust values to equal exactly 1.00 for accurate scoring calculations.")

if gsc_file and ga_file:
    try:
        # --- PARSE DATASETS ---
        df_gsc = None
        if gsc_file.name.endswith('.zip'):
            with zipfile.ZipFile(gsc_file) as z:
                csv_files = [f for f in z.namelist() if f.endswith('.csv') and not f.startswith('__MACOSX')]
                if csv_files:
                    target_file = next((f for f in csv_files if "dates" in f.lower() or "pages" in f.lower() or "queries" in f.lower()), csv_files[0])
                    with z.open(target_file) as f:
                        df_gsc = robust_read_csv(f)
        else:
            df_gsc = robust_read_csv(gsc_file)
            
        df_ga = robust_read_csv(ga_file)

        if df_gsc is not None and df_ga is not None:
            df_gsc.columns = df_gsc.columns.str.strip()
            df_ga.columns = df_ga.columns.str.strip()
            
            # --- DEEP GSC COMPARATIVE EXTRACTION ---
            gsc_curr_clicks = next((c for c in df_gsc.columns if 'clicks' in c.lower() and ('last' in c.lower() or 'current' in c.lower())), None)
            gsc_prev_clicks = next((c for c in df_gsc.columns if 'clicks' in c.lower() and 'prev' in c.lower()), None)
            
            gsc_curr_impr = next((c for c in df_gsc.columns if 'impressions' in c.lower() and ('last' in c.lower() or 'current' in c.lower())), None)
            gsc_prev_impr = next((c for c in df_gsc.columns if 'impressions' in c.lower() and 'prev' in c.lower()), None)
            
            gsc_curr_ctr = next((c for c in df_gsc.columns if 'ctr' in c.lower() and ('last' in c.lower() or 'current' in c.lower())), None)
            gsc_prev_ctr = next((c for c in df_gsc.columns if 'ctr' in c.lower() and 'prev' in c.lower()), None)
            
            gsc_curr_pos = next((c for c in df_gsc.columns if 'position' in c.lower() and ('last' in c.lower() or 'current' in c.lower())), None)
            gsc_prev_pos = next((c for c in df_gsc.columns if 'position' in c.lower() and 'prev' in c.lower()), None)

            # Execution Mapping
            c_clicks = clean_and_sum(df_gsc, gsc_curr_clicks)
            p_clicks = clean_and_sum(df_gsc, gsc_prev_clicks)
            c_impr = clean_and_sum(df_gsc, gsc_curr_impr)
            p_impr = clean_and_sum(df_gsc, gsc_prev_impr)
            c_ctr = clean_and_mean(df_gsc, gsc_curr_ctr)
            p_ctr = clean_and_mean(df_gsc, gsc_prev_ctr)
            c_pos = clean_and_mean(df_gsc, gsc_curr_pos)
            p_pos = clean_and_mean(df_gsc, gsc_prev_pos)

            # --- DEEP GA4 COMPARATIVE EXTRACTION ---
            ga_curr_sess = next((c for c in df_ga.columns if 'sessions' in c.lower() and ('last' in c.lower() or 'current' in c.lower() or 'active' in c.lower())), None)
            ga_prev_sess = next((c for c in df_ga.columns if 'sessions' in c.lower() and 'prev' in c.lower()), None)
            
            ga_curr_users = next((c for c in df_ga.columns if 'user' in c.lower() and ('last' in c.lower() or 'current' in c.lower() or 'active' in c.lower())), None)
            ga_prev_users = next((c for c in df_ga.columns if 'user' in c.lower() and 'prev' in c.lower()), None)
            
            ga_curr_conv = next((c for c in df_ga.columns if ('conversion' in c.lower() or 'key event' in c.lower()) and ('last' in c.lower() or 'current' in c.lower())), None)
            ga_prev_conv = next((c for c in df_ga.columns if ('conversion' in c.lower() or 'key event' in c.lower()) and 'prev' in c.lower()), None)

            c_sess = clean_and_sum(df_ga, ga_curr_sess)
            p_sess = clean_and_sum(df_ga, ga_prev_sess)
            c_users = clean_and_sum(df_ga, ga_curr_users)
            p_users = clean_and_sum(df_ga, ga_prev_users)
            c_conv = clean_and_sum(df_ga, ga_curr_conv)
            p_conv = clean_and_sum(df_ga, ga_prev_conv)

            # --- DELTA ANALYSIS ENGINE ---
            def delta_pct(curr, prev):
                if prev <= 0: return 0.0
                return ((curr - prev) / prev) * 100
                
            def delta_pos(curr, prev):
                # Negative numeric movement in average position means your pages are moving closer to spot #1 (improving)
                if prev <= 0: return 0.0
                return prev - curr 

            d_clicks = delta_pct(c_clicks, p_clicks)
            d_impr = delta_pct(c_impr, p_impr)
            d_ctr = delta_pct(c_ctr, p_ctr)
            d_pos = delta_pos(c_pos, p_pos)
            
            d_sess = delta_pct(c_sess, p_sess)
            d_users = delta_pct(c_users, p_users)
            d_conv = delta_pct(c_conv, p_conv)

            # --- COMPREHENSIVE PROJECT SCORING ENGINE ---
            # Visibility components (Impressions & Rankings)
            score_vis = (d_impr * 0.70) + (d_pos * 15.0)
            score_vis = min(max(score_vis, -25), 25)
            
            # Acquisition components (Organic Clicks & GA Traffic)
            score_acq = (d_clicks * 0.50) + (d_sess * 0.50)
            score_acq = min(max(score_acq, -30), 30)
            
            # Engagement/Action components (Conversions & Core CTR improvements)
            score_eng = (d_conv * 0.70) + (d_ctr * 0.30)
            score_eng = min(max(score_eng, -25), 25)
            
            # Calculate final health score out of 100 points
            weighted_score = 70 + (score_vis * w_vis * 4) + (score_acq * w_acq * 3.33) + (score_eng * w_eng * 4)
            final_project_score = min(max(int(weighted_score), 0), 100)

            # --- PERFORMANCE VIEW INTERFACE ---
            st.subheader("🎯 Automated Project Evaluation Score")
            sc_1, sc_2 = st.columns([1, 2])
            
            with sc_1:
                st.metric(label="Calculated Health Score", value=f"{final_project_score} / 100")
                if final_project_score >= 80:
                    st.success("🔥 **Strong Organic Growth:** The project shows a significant upward trend across almost all tracked acquisition funnels.")
                elif final_project_score >= 60:
                    st.info("📈 **Holding Steady:** The performance vectors are maintaining stability across your current tracking window.")
                else:
                    st.warning("⚠️ **Correction Needed:** Multiple acquisition and search channels are currently lagging behind their historical baselines.")
            
            with sc_2:
                growth_summary_data = pd.DataFrame({
                    'Analytical Dimensions': ['Impressions Growth', 'Organic Clicks Growth', 'GA Traffic Sessions', 'User Base Shift', 'Conversion Vol. Shift'],
                    'Growth Rate %': [d_impr, d_clicks, d_sess, d_users, d_conv]
                })
                fig = px.bar(growth_summary_data, x='Growth Rate %', y='Analytical Dimensions', 
                             orientation='h', color='Growth Rate %', text_auto='.1f',
                             color_continuous_scale=px.colors.diverging.RdYlGn,
                             title="Multi-Channel Metric Trajectory Map")
                st.plotly_chart(fig, use_container_width=True)

            # --- EXTRA COMPARISON METRIC TABLE PANELS ---
            st.markdown("---")
            st.subheader("📊 Deep Comparative Performance Matrix")
            
            deep_matrix = pd.DataFrame({
                'Tracked Data Attribute': [
                    'Google Search Impressions (Visibility)', 
                    'Average Ranking Position (SEO Status)', 
                    'Organic Clicks Volume (Acquisition)',
                    'Average CTR Rate % (Engagement)',
                    'Google Analytics Total Sessions (Traffic)',
                    'Active User Count (Audience Volume)',
                    'Goal Conversions / Key Events (Value Generated)'
                ],
                'Previous 3 Months': [
                    f"{int(p_impr):,}", f"{p_pos:.2f}", f"{int(p_clicks):,}", f"{p_ctr:.2f}%",
                    f"{int(p_sess):,}", f"{int(p_users):,}", f"{int(p_conv):,}"
                ],
                'Current 3 Months': [
                    f"{int(c_impr):,}", f"{c_pos:.2f}", f"{int(c_clicks):,}", f"{c_ctr:.2f}%",
                    f"{int(c_sess):,}", f"{int(c_users):,}", f"{int(c_conv):,}"
                ],
                'Net Growth Delta %': [
                    f"{d_impr:+.1f}%", f"{d_pos:+.2f} positions", f"{d_clicks:+.1f}%", f"{d_ctr:+.1f}%",
                    f"{d_sess:+.1f}%", f"{d_users:+.1f}%", f"{d_conv:+.1f}%"
                ]
            })
            st.table(deep_matrix)
            
        else:
            st.error("❌ Failed to parse structures. Verify that the files match standard GSC/GA formatting.")
    except Exception as e:
        st.error(f"Processing structural exception: {e}. Confirm you enabled the 'Compare' option when exporting your analytics.")
else:
    st.info("💡 **Deep Comparison Engine Online:** Drop your consolidated comparison exports in the sidebar to run the multi-metric audit.")
