import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
from itertools import cycle

# Set Streamlit page configuration
st.set_page_config(page_title="SEO Analysis Dashboard", layout="wide")

# Company folder and file mapping
companies = {
    "Abed Tahhan": {
        "seo_path": "Abed Tahhan/csv",
        "products_path": "Abed_Csv"
    },
    "Beytech": {
        "seo_path": "Beytech/csv",
        "products_path": "Beytech_Csv"
    },
    "Hamdan electronics": {
        "seo_path": "Hamdan electronics/csv",
        "products_path": "Hamdan_Csv"
    }
}

# Sidebar: Select companies for comparison
st.sidebar.title("📊 Company Selector")
comparison_mode = st.sidebar.checkbox("Enable Comparison Mode", False)

if comparison_mode:
    selected_companies = st.sidebar.multiselect(
        "Choose Companies to Compare", 
        list(companies.keys()),
        default=list(companies.keys())[:2]
    )
    color_cycle = cycle(px.colors.qualitative.Plotly)  # For consistent colors in comparison charts
    if comparison_mode and len(selected_companies) == 0:
        st.warning("⚠️ Please select at least one company to compare.")
        st.stop()
else:
    selected_company = st.sidebar.selectbox("Choose a Company", list(companies.keys()))
    selected_companies = [selected_company]
    


# Cache the data loading
@st.cache_data
def load_company_data(seo_path, products_path):
    data = {
        "meta_data": pd.read_csv(os.path.join(seo_path, "meta_data.csv")),
        "backlinks": pd.read_csv(os.path.join(products_path, "backlinks.csv")),
        "navbar": pd.read_csv(os.path.join(seo_path, "navbar.csv")),
        "seo_keywords": pd.read_csv(os.path.join(seo_path, "seo_keywords.csv")),
        "tfidf_keywords": pd.read_csv(os.path.join(seo_path, "tfidf_keywords.csv")),
        "products":  pd.read_csv(os.path.join(products_path, "cleaned_Csv.csv"), parse_dates=["Timestamp"])
    }
    return data

# Load all selected companies' data
all_data = {}
for company_name in selected_companies:
    company = companies[company_name]
    all_data[company_name] = load_company_data(company["seo_path"], company["products_path"])

# Title
if comparison_mode:
    st.title(f"🔍 SEO Analysis Comparison: {' vs '.join(selected_companies)}")
else:
    st.title(f"🔍 SEO Analysis Dashboard for {selected_companies[0]}")

# Helper function for comparison charts
def create_comparison_chart(data_dict, metric_func, title, chart_type='bar'):
    """Create a comparison chart across companies for a given metric"""
    metrics = {}
    for company_name, data in data_dict.items():
        metrics[company_name] = metric_func(data)
    
    df = pd.DataFrame.from_dict(metrics, orient='index', columns=['Value'])
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'Company'}, inplace=True)
    
    if chart_type == 'bar':
        fig = px.bar(df, x='Company', y='Value', title=title, color='Company')
    elif chart_type == 'pie':
        fig = px.pie(df, values='Value', names='Company', title=title)
    else:
        fig = px.line(df, x='Company', y='Value', title=title)
    
    return fig


#Backlinks
with st.container():
    st.subheader("🔗 Backlink Platforms Comparison" if comparison_mode else "🔗 Backlink Platforms")
    
    if comparison_mode: 
        # Create a combined backlinks DataFrame for comparison
        
        backlinks_dfs = []
        for company_name, data in all_data.items():
            df = data["backlinks"].copy()
            df['Company'] = company_name
            backlinks_dfs.append(df)
        
        combined_backlinks = pd.concat(backlinks_dfs)

        # Use 'Platform' if exists, otherwise try 'Type'
        platform_col = None
        for col in ["Platform", "Type"]:
            if col in combined_backlinks.columns:
                platform_col = col
                break

        if platform_col:
            # Comparison of total backlinks
            total_backlinks = combined_backlinks.groupby('Company').size().reset_index(name='Count')
            fig_total = px.bar(
                total_backlinks,
                x='Company',
                y='Count',
                title="Total Backlinks Comparison",
                color='Company',
                color_discrete_sequence=px.colors.qualitative.Plotly
            )
            st.plotly_chart(fig_total, use_container_width=True)

            platform_counts = combined_backlinks.groupby(['Company', platform_col]).size().reset_index(name='Count')

            # Create a complete grid of all companies and all platforms
            all_companies = combined_backlinks['Company'].unique()
            all_platforms = combined_backlinks[platform_col].unique()
            full_index = pd.MultiIndex.from_product([all_companies, all_platforms], names=['Company', platform_col])
            
            # Reindex and fill missing combinations with zero
            platform_counts = platform_counts.set_index(['Company', platform_col]).reindex(full_index, fill_value=0).reset_index()

            fig_platform = px.bar(
                platform_counts,
                x='Company',
                y='Count',
                color=platform_col,
                title=f"Backlinks by {platform_col} Comparison",
                barmode='group',
                category_orders={
                    "Company": list(all_data.keys()),
                    platform_col: sorted([str(p) for p in all_platforms])
                }
            )

            st.plotly_chart(fig_platform, use_container_width=True)
        else:
            st.warning("No platform or type column found in backlinks data.")
    
    else:
        # Single company view
        backlinks_df = all_data[selected_companies[0]]["backlinks"]

        # Use 'Platform' if exists, otherwise try 'Type'
        platform_col = None
        for col in ["Platform", "Type"]:
            if col in backlinks_df.columns:
                platform_col = col
                break

        if platform_col:
            backlink_counts = backlinks_df[platform_col].value_counts().reset_index()
            backlink_counts.columns = [platform_col, "Count"]

            fig = px.pie(
                backlink_counts,
                values="Count",
                names=platform_col,
                title="Distribution of Backlink Platforms",
                hole=0.4
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No platform or type column found in backlinks data.")

# --- Keyword Comparison
st.subheader("🔑 Keyword Insights Comparison" if comparison_mode else "🔑 Keyword Insights")

if comparison_mode:
    # Top keywords comparison
    top_n = st.slider("Number of top keywords to compare", 5, 20, 10)
    
    # Create a combined keywords DataFrame for comparison
    keywords_dfs = []
    for company_name, data in all_data.items():
        df = data["seo_keywords"].copy()
        df['Company'] = company_name
        keywords_dfs.append(df)
    
    combined_keywords = pd.concat(keywords_dfs)
    
    # Get top keywords across all companies
    top_keywords_all = combined_keywords.groupby('Keyword')['Count'].sum().nlargest(top_n).index
    
    # Filter for only the top keywords
    filtered_keywords = combined_keywords[combined_keywords['Keyword'].isin(top_keywords_all)]
    
    # Create comparison chart
    fig = px.bar(
        filtered_keywords,
        x='Keyword',
        y='Count',
        color='Company',
        title=f"Top {top_n} Keywords Comparison",
        barmode='group'
    )
    fig.update_layout(xaxis={'categoryorder':'total descending'})
    st.plotly_chart(fig, use_container_width=True)
    
    # Show individual company keyword data side-by-side
    st.markdown("### 📊 Top Keyword Frequency Charts per Company")

    charts_per_row = 2  # You can change this to 3 or more based on screen space
    companies = list(all_data.keys())
    rows = (len(companies) + charts_per_row - 1) // charts_per_row

    for i in range(rows):
        cols = st.columns(charts_per_row)
        for j in range(charts_per_row):
            idx = i * charts_per_row + j
            if idx < len(companies):
                company_name = companies[idx]
                top_keywords = all_data[company_name]["seo_keywords"].sort_values("Count", ascending=False).head(top_n)
                fig_freq = px.bar(
                    top_keywords,
                    x="Count",
                    y="Keyword",
                    orientation="h",
                    title=f"{company_name} - Top {top_n} Keywords",
                    color="Count",
                    color_continuous_scale="Tealgrn"
                )
                fig_freq.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    height=top_n * 30 + 150
                )
                with cols[j]:
                    st.plotly_chart(fig_freq, use_container_width=True)

else:
    # Single company view for keywords
    data = all_data[selected_companies[0]]
    col1, col2 = st.columns([1.2, 1])
    
    with col1:
        st.subheader("### 📈 Top Keywords by Frequency")
        top_keywords = data["seo_keywords"].sort_values("Count", ascending=False).head(20)
        fig_freq = px.bar(
            top_keywords,
            x="Count",
            y="Keyword",
            orientation="h",
            title="Top 20 Keywords by Frequency",
            color="Count",
            color_continuous_scale="Tealgrn"
        )
        fig_freq.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    height=20 * 30 + 150
                )
        st.plotly_chart(fig_freq, use_container_width=True)


# --- Product Data Comparison
st.sidebar.header("🛍️ Filter Products")
if comparison_mode:
    # Apply the same filters to all companies being compared
    products_dfs = []
    for company_name in selected_companies:
        products_df = all_data[company_name]["products"].copy()
        products_df['Company'] = company_name
        products_dfs.append(products_df)
    
    combined_products = pd.concat(products_dfs)
    
    # Filters
    main_categories = ["All"] + sorted(combined_products["Main Category"].dropna().unique())
    selected_main = st.sidebar.selectbox("Main Category", main_categories)
    
    price_min = float(combined_products["Current Price"].min())
    price_max = float(combined_products["Current Price"].max())
    price_range = st.sidebar.slider("Price Range", price_min, price_max, (price_min, price_max))

    
    # Apply filters
    filtered_products = combined_products.copy()
    if selected_main != "All":
        filtered_products = filtered_products[filtered_products["Main Category"] == selected_main]
    
    filtered_products = filtered_products[
        (filtered_products["Current Price"] >= price_range[0]) & 
        (filtered_products["Current Price"] <= price_range[1])
    ]
else:
    # Single company product filters
    products_df = all_data[selected_companies[0]]["products"]
    main_categories = ["All"] + sorted(products_df["Main Category"].dropna().unique())
    selected_main = st.sidebar.selectbox("Main Category", main_categories)

    price_min = float(products_df["Current Price"].min())
    price_max = float(products_df["Current Price"].max())
    price_range = st.sidebar.slider("Price Range", price_min, price_max, (price_min, price_max))

    # Apply filters
    filtered_products = products_df.copy()
    if selected_main != "All":
        filtered_products = filtered_products[filtered_products["Main Category"] == selected_main]
    
    filtered_products = filtered_products[
        (filtered_products["Current Price"] >= price_range[0]) & 
        (filtered_products["Current Price"] <= price_range[1])
    ]

# --- Product Overview Comparison
with st.container():
    st.subheader("📦 Product Overview Comparison" if comparison_mode else "📦 Product Overview")
    
    if comparison_mode:
        # Show product count by company
        product_counts = filtered_products.groupby('Company').size().reset_index(name='Count')
        fig = px.bar(
            product_counts,
            x='Company',
            y='Count',
            title="Product Count Comparison",
            color='Company',
            color_discrete_sequence=px.colors.qualitative.Plotly
        )
        st.plotly_chart(fig, use_container_width=True)

# --- Product Visualizations
col3, col4 = st.columns(2)
with col3:
    st.subheader("🧺 Product Categories Count")
    
    if comparison_mode:
        if "Product Category" in filtered_products.columns:
            category_counts = filtered_products.groupby(['Company', 'Product Category']).size().reset_index(name='Count')
            fig = px.bar(
                category_counts,
                x='Product Category',
                y='Count',
                color='Company',
                barmode='group',
                title="Product Category Count Comparison"
            )
            st.plotly_chart(fig, use_container_width=True)
        elif "Main Category" in filtered_products.columns:
            category_counts = filtered_products.groupby(['Company', 'Main Category']).size().reset_index(name='Count')
            fig = px.bar(
                category_counts,
                x='Main Category',
                y='Count',
                color='Company',
                barmode='group',
                title="Main Category Count Comparison"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No category column available for comparison.")
    else:
        if "Product Category" in filtered_products.columns:
            st.bar_chart(filtered_products["Product Category"].value_counts())
        elif "Main Category" in filtered_products.columns:
            st.bar_chart(filtered_products["Main Category"].value_counts())
        else:
            st.warning("No category column available for this company.")

with col4:
    st.subheader("💰 Price Distribution")
    
    if not filtered_products.empty:
        if comparison_mode:
            fig = px.histogram(
                filtered_products,
                x='Current Price',
                color='Company',
                marginal='rug',
                title="Price Distribution Comparison",
                barmode='overlay',
                opacity=0.7
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            price_hist = (
                alt.Chart(filtered_products)
                .mark_bar()
                .encode(
                    alt.X("Current Price", bin=True),
                    y='count()'
                )
                .properties(width=400, height=300)
            )
            st.altair_chart(price_hist, use_container_width=True)
    else:
        st.warning("No products to show for this filter.")


# --- Export Visualizations
with st.expander("📤 Export Visualizations"):
    st.markdown("You can right-click on any plot and **save as image**.")
    st.markdown("To export as PDF, use browser print/save feature or use a screenshot + PDF tool.")

