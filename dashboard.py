"""
Interactive dashboard for monitoring FIDC portfolios.
Final version with tabs for Portfolio Summary, Deal by Deal Analysis, 
and Macroeconomic Analysis. All UI elements are in English.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Portfolio Monitoring Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Data Folder Path ---
# Define o caminho para o diretório de dados de forma relativa ao script
script_dir = os.path.dirname(__file__)
DATA_DIR = os.path.join(script_dir, "data")

# --- Helper Functions ---
@st.cache_data
def load_all_data(data_directory):
    """
    Loads all CSV files from the specified data directory.
    """
    files = {
        "cvm": os.path.join(data_directory, "CVM_Data.csv"),
        "covenants": os.path.join(data_directory, "Specific_Covenants.csv"),
        "macro": os.path.join(data_directory, "Macro.csv"),
    }
    
    dataframes = {}
    for key, path in files.items():
        if not os.path.exists(path):
            st.error(f"ERROR: File '{path}' not found. Please check the path.")
            return None
        try:
            dataframes[key] = pd.read_csv(path, sep=';', encoding='latin1')
            if dataframes[key].columns[0].startswith('ï»¿'):
                dataframes[key].rename(columns={dataframes[key].columns[0]: dataframes[key].columns[0][3:]}, inplace=True)
        except Exception as e:
            st.error(f"Error loading {path}: {e}")
            return None

    # --- Specific DataFrame Processing ---
    
    # CVM Data
    df_cvm = dataframes['cvm']
    df_cvm['data_referencia'] = pd.to_datetime(df_cvm['data_referencia'], errors='coerce')
    df_cvm = df_cvm.sort_values(by=['fundo', 'data_referencia'])
    df_cvm['retorno_junior_acumulado'] = df_cvm.groupby('fundo')['retorno_junior'].transform(
        lambda x: (1 + pd.to_numeric(x, errors='coerce').fillna(0) / 100).cumprod() - 1
    )
    dataframes['cvm'] = df_cvm

    # Specific Covenants
    df_cov = dataframes['covenants']
    df_cov['Date'] = pd.to_datetime(df_cov['Date'], errors='coerce')
    for col in ['Value', 'Threshold']:
        if col in df_cov.columns:
            df_cov[col] = pd.to_numeric(df_cov[col].astype(str).str.replace(',', '.'), errors='coerce')
    dataframes['covenants'] = df_cov

    # Macro Data
    df_macro = dataframes['macro']
    df_macro['Date'] = pd.to_datetime(df_macro['Date'], errors='coerce', dayfirst=True)
    for col in df_macro.columns:
        if col != 'Date':
            df_macro[col] = pd.to_numeric(df_macro[col].astype(str).str.replace(',', '.'), errors='coerce')
    dataframes['macro'] = df_macro

    return dataframes

def style_compliance_table(df_to_style):
    """ Styles the compliance table based on status. """
    def color_cell(val):
        if val == 'Flag': return 'background-color: #ffcccb'
        if val == 'OK': return 'background-color: #90ee90'
        if val == 'N/A': return 'background-color: #d3d3d3'
        return ''
    return df_to_style.style.applymap(color_cell)

# --- Start of Dashboard ---
st.title("📈 Portfolio Monitoring Dashboard")

with st.spinner('Loading data... Please wait.'):
    all_data = load_all_data(DATA_DIR)

if all_data:
    df_cvm = all_data['cvm']
    df_covenants = all_data.get('covenants')
    df_macro = all_data.get('macro')

    # --- Tab Creation ---
    tab1, tab2, tab3 = st.tabs([" Portfolio Summary ", " Deal by Deal Analysis ", " Macro Analysis "])

    # --- TAB 1: PORTFOLIO SUMMARY ---
    with tab1:
        st.header("Overall Portfolio Summary")
        latest_data_all_funds = df_cvm.sort_values('data_referencia').groupby('fundo').tail(1)

        st.subheader("Key Metrics Overview (Latest Month)")
        summary_table = latest_data_all_funds[['fundo', 'net_worth', 'pv_credit_rights', 'pdd']].set_index('fundo')
        st.dataframe(summary_table.style.format("R$ {:,.2f}"))
        
        st.subheader("CVM Covenant Compliance Status (Latest Month)")
        status_cols = ['fundo'] + sorted([col for col in df_cvm.columns if col.startswith('status_')])
        if len(status_cols) > 1:
            compliance_table = latest_data_all_funds[status_cols].set_index('fundo')
            st.dataframe(style_compliance_table(compliance_table))
        else:
            st.info("No CVM covenant status columns found in the data.")

    # --- TAB 2: DEAL BY DEAL ANALYSIS ---
    with tab2:
        st.sidebar.header("Deal by Deal Filters")
        fundos_disponiveis = sorted(df_cvm['fundo'].unique())
        selected_fund = st.sidebar.selectbox('Select a Fund (Deal):', options=fundos_disponiveis, key='deal_selector')
        
        df_fund_cvm = df_cvm[df_cvm['fundo'] == selected_fund].copy()
        
        st.header(f"Fund Analysis: {selected_fund}")
        
        if not df_fund_cvm.empty:
            latest_data_cvm = df_fund_cvm.iloc[-1]
            kpi_cols = st.columns(3)
            kpi_cols[0].metric("Net Worth", f"R$ {latest_data_cvm['net_worth']/1e6:,.2f} M")
            kpi_cols[1].metric("PV of Credit Rights", f"R$ {latest_data_cvm['pv_credit_rights']/1e6:,.2f} M")
            kpi_cols[2].metric("PDD", f"R$ {latest_data_cvm['pdd']/1e6:,.2f} M")
        
        st.subheader("CVM Data Analysis")
        if not df_fund_cvm.empty:
            graph_col1, graph_col2 = st.columns(2)
            
            with graph_col1:
                st.subheader("1. Net Worth, PV & PDD")
                fig1 = go.Figure()
                fig1.add_trace(go.Bar(x=df_fund_cvm['data_referencia'], y=df_fund_cvm['pdd'], name='PDD', marker_color='lightcoral'))
                fig1.add_trace(go.Scatter(x=df_fund_cvm['data_referencia'], y=df_fund_cvm['net_worth'], name='Net Worth', mode='lines', line=dict(color='royalblue')))
                fig1.add_trace(go.Scatter(x=df_fund_cvm['data_referencia'], y=df_fund_cvm['pv_credit_rights'], name='PV of Credit Rights', mode='lines', line=dict(color='mediumseagreen')))
                fig1.update_layout(barmode='overlay', legend_title_text='Metric', xaxis_title='Date', yaxis_title='Value (BRL)')
                st.plotly_chart(fig1, use_container_width=True)
            
            with graph_col2:
                st.subheader("2. Subordination vs. Threshold")
                sub_cols_to_plot = []
                for col_name in df_fund_cvm.columns:
                    if 'subordination_' in col_name:
                        threshold_col = col_name.replace('subordination', 'threshold')
                        if threshold_col in df_fund_cvm.columns and pd.notna(latest_data_cvm.get(threshold_col)):
                            sub_cols_to_plot.append(col_name)
                            sub_cols_to_plot.append(threshold_col)
                if sub_cols_to_plot:
                    df_melt2 = df_fund_cvm.melt(id_vars='data_referencia', value_vars=list(set(sub_cols_to_plot)), var_name='Metric', value_name='Ratio')
                    fig2 = px.line(df_melt2, x='data_referencia', y='Ratio', color='Metric', labels={"data_referencia": "Date", "Ratio": "Subordination Ratio"})
                    fig2.update_yaxes(tickformat=".2%")
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.warning("No CVM subordination metrics with defined thresholds found for this fund.")

            with graph_col1:
                st.subheader("3. Junior Quota Cumulative Return")
                fig3 = px.area(df_fund_cvm, x='data_referencia', y='retorno_junior_acumulado', labels={"data_referencia": "Date", "retorno_junior_acumulado": "Cumulative Return"})
                fig3.update_yaxes(tickformat=".2%")
                st.plotly_chart(fig3, use_container_width=True)

            with graph_col2:
                st.subheader("4. Delinquency by Range (% of PV)")
                delinq_cols = [col for col in df_fund_cvm.columns if col.startswith('delinq_ratio_')]
                delinq_order = ['delinq_ratio_30', 'delinq_ratio_31_60', 'delinq_ratio_61_90', 'delinq_ratio_91_120', 'delinq_ratio_121_150', 'delinq_ratio_151_180', 'delinq_ratio_181_360', 'delinq_ratio_over_360']
                if delinq_cols:
                    df_melt4 = df_fund_cvm.melt(id_vars='data_referencia', value_vars=delinq_cols, var_name='Delinquency Bucket', value_name='Percent of PV')
                    final_delinq_order_labels = [label.replace('delinq_ratio_', 'Overdue ') for label in delinq_order]
                    fig4 = px.bar(df_melt4, x='data_referencia', y='Percent of PV', color='Delinquency Bucket', barmode='stack', category_orders={'Delinquency Bucket': final_delinq_order_labels})
                    fig4.update_yaxes(tickformat=".2%")
                    st.plotly_chart(fig4, use_container_width=True)
                else:
                    st.warning("No delinquency metrics found for this fund.")

            with graph_col1:
                st.subheader("5. Monthly Origination vs. Net Allocation")
                fig5 = make_subplots(specs=[[{"secondary_y": True}]])
                fig5.add_trace(go.Bar(x=df_fund_cvm['data_referencia'], y=df_fund_cvm['vl_dicred_aquis_mes'], name='Origination (BRL)'), secondary_y=False)
                fig5.add_trace(go.Scatter(x=df_fund_cvm['data_referencia'], y=df_fund_cvm['net_allocation'], name='Net Allocation (%)', mode='lines'), secondary_y=True)
                fig5.update_yaxes(title_text="Origination Value (BRL)", secondary_y=False)
                fig5.update_yaxes(title_text="Net Allocation", secondary_y=True, tickformat=".2%")
                st.plotly_chart(fig5, use_container_width=True)
            
            with graph_col2:
                st.subheader("6. Receivables Curve (Aging)")
                prazo_cols = [col for col in df_fund_cvm.columns if col.startswith('CR_due_')]
                prazo_order = ['CR_due_30', 'CR_due_31_60', 'CR_due_61_90', 'CR_due_91_120', 'CR_due_121_150', 'CR_due_151_180', 'CR_due_181_360', 'CR_due_over_360']
                if prazo_cols:
                    df_melt6 = df_fund_cvm.melt(id_vars='data_referencia', value_vars=prazo_cols, var_name='Aging Bucket', value_name='Value (BRL)')
                    final_prazo_order_labels = [label.replace('CR_due_', 'Term ') for label in prazo_order]
                    fig6 = px.bar(df_melt6, x='data_referencia', y='Value (BRL)', color='Aging Bucket', barmode='stack', category_orders={'Aging Bucket': final_prazo_order_labels})
                    st.plotly_chart(fig6, use_container_width=True)
                else:
                    st.warning("No aging metrics found for this fund.")
        else:
            st.warning("No CVM data available for this fund.")
        
        st.markdown("---")
        st.subheader("Specific Covenant Analysis")
        if df_covenants is not None:
            df_fund_cov = df_covenants[df_covenants['Deal'] == selected_fund].copy()
            if not df_fund_cov.empty:
                st.markdown("##### Covenant Performance Over Time")
                covenant_table = df_fund_cov.pivot_table(index='Date', columns='Metric', values='Value').sort_index(ascending=False)
                status_table = df_fund_cov.pivot_table(index='Date', columns='Metric', values='Status', aggfunc='first').sort_index(ascending=False)
                status_table = status_table.reindex(index=covenant_table.index, columns=covenant_table.columns)
                def color_covenant_cells(data):
                    style_df = pd.DataFrame('', index=data.index, columns=data.columns)
                    for r_idx, row in status_table.iterrows():
                        for c_idx, status_val in row.items():
                            if status_val == 'FLAG': style_df.loc[r_idx, c_idx] = 'background-color: #ffcccb'
                            elif status_val == 'OK': style_df.loc[r_idx, c_idx] = 'background-color: #90ee90'
                    return style_df
                st.dataframe(covenant_table.style.format("{:,.2f}").apply(color_covenant_cells, axis=None))
                st.markdown("##### Covenant Graphical Analysis")
                available_metrics = sorted(df_fund_cov['Metric'].unique())
                selected_metric = st.selectbox("Select a metric to visualize:", options=available_metrics)
                df_metric_plot = df_fund_cov[df_fund_cov['Metric'] == selected_metric]
                fig_cov = go.Figure()
                fig_cov.add_trace(go.Scatter(x=df_metric_plot['Date'], y=df_metric_plot['Value'], name='Metric Value', mode='lines+markers'))
                fig_cov.add_trace(go.Scatter(x=df_metric_plot['Date'], y=df_metric_plot['Threshold'], name='Threshold', mode='lines', line=dict(dash='dot', color='red')))
                fig_cov.update_layout(title=f"Performance of: {selected_metric}", xaxis_title="Date", yaxis_title="Value")
                st.plotly_chart(fig_cov, use_container_width=True)
            else:
                st.warning("No specific covenant data found for this fund.")
        else:
            st.info("File 'Specific_Covenants.csv' not loaded.")
            

    # --- TAB 3: MACRO ANALYSIS ---
    with tab3:
        st.header("Macroeconomic Analysis")
        if df_macro is not None:
            df_macro_analysis = df_macro.set_index('Date').sort_index()

            st.subheader("1. Total Credit Portfolio Brazil")
            credit_cols = ['Credit_Portfolio_Total_BRL_mn', 'Credit_Portfolio_Corporate_BRL_mn', 'Credit_Portfolio_Retail_BRL_mn']
            fig_credit = px.line(df_macro_analysis, y=credit_cols, title="Credit Portfolio Evolution (BRL mn)")
            st.plotly_chart(fig_credit, use_container_width=True)

            st.subheader("2. Delinquency Trends")
            col1, col2 = st.columns(2)
            with col1:
                delinq_cols = ['Delinquency_15-90d_Total_%', 'Delinquency_15-90d_Corporate_%', 'Delinquency_15-90d_Retail_%']
                fig_delinq_total = px.line(df_macro_analysis, y=delinq_cols, title="General Delinquency (15-90 days)")
                st.plotly_chart(fig_delinq_total, use_container_width=True)
                
                default_corp_cols = ['Default_Rate__Corporate_SMBs_%', 'Default_Rate_Corporate_Large_%']
                fig_default_corp = px.line(df_macro_analysis, y=default_corp_cols, title="Corporate Default Rates")
                st.plotly_chart(fig_default_corp, use_container_width=True)
            with col2:
                default_personal_cols = ['Default_Rate_Personal_NonPayroll_%', 'Default_Rate_Personal_Payroll_Private_%', 'Default_Rate_Revolving_Credit_Card_%']
                fig_default_personal = px.line(df_macro_analysis, y=default_personal_cols, title="Personal Default Rates")
                st.plotly_chart(fig_default_personal, use_container_width=True)

            st.subheader("3. Interest Rates")
            interest_cols = ['Interest_Rate_NonEarmarked_Corporate_%am', 'Interest_Rate_NonEarmarked_Retail_%am']
            fig_interest = px.line(df_macro_analysis, y=interest_cols, title="Non-Earmarked Interest Rates (% a.m.)")
            
            latest_rates = df_macro_analysis[interest_cols].dropna().iloc[-1]
            spread = (latest_rates['Interest_Rate_NonEarmarked_Retail_%am'] / latest_rates['Interest_Rate_NonEarmarked_Corporate_%am']) - 1
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.plotly_chart(fig_interest, use_container_width=True)
            with col2:
                st.metric("Retail vs. Corporate Spread", f"{spread:.2%}", help="Retail Rate / Corporate Rate - 1")

            st.subheader("4. Activity")
            col1, col2 = st.columns(2)
            with col1:
                fig_unemployment = px.line(df_macro_analysis, y='Unemployment_Rate_PNADC_%', title="Unemployment Rate (PNADC)")
                st.plotly_chart(fig_unemployment, use_container_width=True)
            with col2:
                fig_inflation = px.line(df_macro_analysis, y='Inflation_IPC-Br_%', title="Inflation (IPC-Br)")
                st.plotly_chart(fig_inflation, use_container_width=True)

            st.subheader("5. Fiscal Policy")
            col1, col2 = st.columns(2)
            with col1:
                fiscal_debt_cols = ['Net_Debt_FedGov_CenBank_%GDP', 'Net_Debt_Consolidated_%GDP']
                fig_fiscal_debt = px.line(df_macro_analysis, y=fiscal_debt_cols, title="Net Debt (% GDP)")
                st.plotly_chart(fig_fiscal_debt, use_container_width=True)
            with col2:
                fig_primary_result = px.bar(df_macro_analysis, y='Primary_Result_YTD_ex-FX_BRL_mn', title="Primary Result YTD (BRL mn)")
                st.plotly_chart(fig_primary_result, use_container_width=True)
        else:
            st.info("File 'Macro.csv' not loaded.")
else:
    st.info("Awaiting data load to display the dashboard.")
