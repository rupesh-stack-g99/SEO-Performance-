import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import io

# Set up the Streamlit page
st.set_page_config(page_title="GSC & GA Performance Dashboard", layout="wide")
st.title("📈 3-Month Website Performance Dashboard")
st.subheader("Compare Google Search Console & Google Analytics Data Automatically")

st.markdown("---")

# Sidebar for configuration
st.sidebar.header("⚙️ Configuration")
join_column = st.sidebar.text_input("Common Column to Match On (e.g., Page, Date)", value="Page")

st.sidebar.header("📁 Upload Data Files")
uploaded_file = st.sidebar.file_uploader(
    "Upload GSC & GA Data (Upload 2 CSVs together, or 1 ZIP file)", 
    type=["csv", "zip"], 
    accept_multiple_files=True
)

# Placeholders for our DataFrames
df_gsc = None
df_ga = None

if uploaded_file:
    try:
        # Scenario 1: User uploaded a ZIP file
        if len(uploaded_file) == 1 and uploaded_file[0].name.endswith('.zip'):
            with zipfile.ZipFile(uploaded_file[0]) as z:
                # Get list of file names inside the zip
                file_list = z.namelist()
                csv_files = [f for f in file_list if f.endswith('.csv') and not f.startswith('__MACOSX')]
                
                # Attempt to automatically identify GSC and GA files from the zip
                for file_name in csv_files:
                    lower_name = file_name.lower()
                    with z.open(file_name) as f:
                        if "search" in lower_name or "gsc" in lower_name or "console" in lower_name:
                            df_gsc = pd.read_csv(f)
                        elif "analytics" in lower_name or "ga" in lower_name or "traffic" in lower_name:
                            df_ga = pd.read_csv(f)
            
            if df_gsc is None or df_ga is None:
                st.warning("⚠️ Found a ZIP file, but couldn't auto-distinguish GSC from GA. We loaded the first two CSVs we found instead.")
                # Fallback to just grabbing the first two CSVs in the zip if keywords didn't match
                if len(csv_files) >= 2:
                    with z.open(csv_files[0]) as f: df_gsc = pd.read_csv(f)
                    with z.open(csv_files[1]) as f: df_ga = pd.read_csv(f)

        # Scenario 2: User uploaded multiple files directly (e.g., dragged two CSVs)
        else:
            for file in uploaded_file:
                lower_name = file.name.lower()
                if "search" in lower_name or "gsc" in lower_name or "console" in lower_name:
                    df_gsc = pd.read_csv(file)
                elif "analytics" in lower_name or "ga" in lower_name or "traffic" in lower_name:
                    df_ga = pd.read_csv(file)
            
            # Fallback if names are completely random
            if (df_gsc is None or df_ga is None) and len(uploaded_file) == 2:
                df_gsc = pd.read_csv(uploaded_file[0])
                df_ga = pd.read_csv(uploaded_file[1])

        # --- DATA PROCESSING & DASHBOARD DISPLAY ---
        if df_gsc is not None and df_ga is not None:
            # Clean column names (strip whitespace)
            df_gsc.columns = df_gsc.columns.str.strip()
            df_ga.columns = df_ga.columns.str.strip()
            
            # Merge the datasets
            if join_column in df_gsc.columns and join_column in df_ga.columns:
                merged_df = pd.merge(df_gsc, df_ga, on=join_column, how="inner")
                
                st.success("✅ Data successfully extracted, merged, and processed!")
                
                # --- KPI METRICS ---
                st.subheader("📊 Quick 3-Month Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                clicks = merged_df.get('Clicks', pd.Series([0])).sum()
                impressions = merged_df.get('Impressions', pd.Series([0])).sum()
                sessions = merged_df.get('Sessions', pd.Series([0])).sum()
                conversions = merged_df.get('Conversions', merged_df.get('Transactions', pd.Series([0]))).sum()
                
                col1.metric("Total GSC Clicks", f"{clicks:,}")
                col2.metric("Total GSC Impressions", f"{impressions:,}")
                col3.metric("Total GA Sessions", f"{sessions:,}")
                col4.metric("Total GA Conversions", f"{conversions:,}")
                
                st.markdown("---")
                
                # --- INTERACTIVE CHARTS ---
                st.subheader("📉 Performance Visualization")
                
                if 'Clicks' in merged_df.columns and 'Sessions' in merged_df.columns:
                    fig1 = px.scatter(
                        merged_df, 
                        x='Clicks', 
                        y='Sessions', 
                        hover_name=join_column,
                        title="Correlation: GSC Clicks vs GA Sessions per Page",
                        trendline="ols"
                    )
                    st.plotly_chart(fig1, use_container_width=True)
                
                st.subheader("🏆 Top Performing Pages/Dates")
                metric_to_plot = st.selectbox("Select metric to rank by:", ['Clicks', 'Impressions', 'Sessions'])
                
                top_data = merged_df.sort_values(by=metric_to_plot, ascending=False).head(10)
                fig2 = px.bar(
                    top_data, 
                    x=join_column, 
                    y=metric_to_plot, 
                    title=f"Top 10 Pages by {metric_to_plot}",
                    color=metric_to_plot
                )
                st.plotly_chart(fig2, use_container_width=True)
                
                # --- DATA TABLE ---
                st.subheader("📋 Full Merged Dataset")
                st.dataframe(merged_df, use_container_width=True)
                
                csv_data = merged_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Merged Data as CSV",
                    data=csv_data,
                    file_name="gsc_ga_3month_comparison.csv",
                    mime="text/csv"
                )
                
            else:
                st.error(f"❌ Error: Could not find the column '{join_column}' in one or both files.")
                st.write("Identified GSC Columns:", list(df_gsc.columns))
                st.write("Identified GA Columns:", list(df_ga.columns))
        else:
            st.warning("⚠️ Please ensure you have provided both a Google Search Console file and a Google Analytics file.")

    except Exception as e:
        st.error(f"An error occurred while processing the files: {e}")
else:
    st.info("💡 Please upload either your **ZIP file** containing the CSVs, or select both **GSC and GA CSV files** directly.")
