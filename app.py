import streamlit as st
import pandas as pd
import plotly.express as px

# Set up the Streamlit page
st.set_page_config(page_title="GSC & GA Performance Dashboard", layout="wide")
st.title("📈 3-Month Website Performance Dashboard")
st.subheader("Compare Google Search Console & Google Analytics Data Automatically")

st.markdown("---")

# Sidebar for file uploads
st.sidebar.header("📁 Upload Data Files")
gsc_file = st.sidebar.file_uploader("Upload GSC Data (CSV)", type=["csv"])
ga_file = st.sidebar.file_uploader("Upload GA Data (CSV)", type=["csv"])

# Define the common joining column (usually 'Page', 'Landing Page', or 'Date')
# You can tweak these strings based on your exact column headers
join_column = st.sidebar.text_input("Common Column to Match On (e.g., Page, Date)", value="Page")

if gsc_file and ga_file:
    try:
        # Load the data
        df_gsc = pd.read_csv(gsc_file)
        df_ga = pd.read_csv(ga_file)
        
        # Clean column names (strip whitespace)
        df_gsc.columns = df_gsc.columns.str.strip()
        df_ga.columns = df_ga.columns.str.strip()
        
        # Merge the datasets
        if join_column in df_gsc.columns and join_column in df_ga.columns:
            merged_df = pd.merge(df_gsc, df_ga, on=join_column, how="inner")
            
            st.success("✅ Files successfully merged and processed!")
            
            # --- KPI METRICS ---
            st.subheader("📊 Quick 3-Month Summary")
            col1, col2, col3, col4 = st.columns(4)
            
            # Dynamically guess metrics columns, fallback to 0 if not found
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
            
            # Chart 1: Clicks vs Sessions
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
            
            # Chart 2: Top Pages by Traffic
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
            
            # Download Button
            csv_data = merged_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Merged Data as CSV",
                data=csv_data,
                file_name="gsc_ga_3month_comparison.csv",
                mime="text/csv"
            )
            
        else:
            st.error(f"❌ Error: Could not find the column '{join_column}' in one or both files. Please check your file headers.")
            st.write("GSC Columns:", list(df_gsc.columns))
            st.write("GA Columns:", list(df_ga.columns))

    except Exception as e:
        st.error(f"An error occurred while processing the files: {e}")

else:
    st.info("💡 Please upload both your **GSC** and **GA** CSV files in the sidebar to begin.")
