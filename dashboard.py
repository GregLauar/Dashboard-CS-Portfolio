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

# ===============================================================
# CÓDIGO DE VERIFICAÇÃO DE SENHA - COLE ISSO NO TOPO
# ===============================================================
def check_password():
    """Retorna `True` se o usuário inseriu a senha correta."""

    def password_entered():
        """Verifica se a senha inserida pelo usuário está correta."""
        if st.session_state["password"] == st.secrets["PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.text_input(
        "Type your password to continue", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Incorrect Password")
    return False

if not check_password():
    st.stop()
# ===============================================================
# FIM DO CÓDIGO DE VERIFICAÇÃO
# ===============================================================


# O RESTO DO SEU DASHBOARD COMEÇA AQUI
# Exemplo:
st.title("Dashboard-CS-Portfolio")
st.write("Análises e monitoramento do seu portfólio.")

# ... todo o seu código de cálculos, gráficos e tabelas continua normalmente aqui ...


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
    Carrega todos os arquivos CSV do diretório de dados especificado.
    """
    files = {
        "cvm": os.path.join(data_directory, "CVM_Data.csv"),
        "specific_data": os.path.join(data_directory, "Specific_Data.csv"),
        "macro": os.path.join(data_directory, "Macro.csv"),
    }
    
    dataframes = {}
    for key, path in files.items():
        if not os.path.exists(path):
            st.error(f"ERRO: Arquivo '{path}' não encontrado. Por favor, verifique o caminho.")
            return None
        try:
            dataframes[key] = pd.read_csv(path, sep=';', encoding='latin1')
            # Remove o caractere BOM (Byte Order Mark) se existir no início do cabeçalho
            if dataframes[key].columns[0].startswith('ï»¿'):
                dataframes[key].rename(columns={dataframes[key].columns[0]: dataframes[key].columns[0][3:]}, inplace=True)
        except Exception as e:
            st.error(f"Erro ao carregar {path}: {e}")
            return None

    # --- Processamento Específico dos DataFrames ---
    
    # Dados CVM
    df_cvm = dataframes['cvm']
    df_cvm['data_referencia'] = pd.to_datetime(df_cvm['data_referencia'], errors='coerce')
    df_cvm = df_cvm.sort_values(by=['fundo', 'data_referencia'])
    df_cvm['retorno_junior_acumulado'] = df_cvm.groupby('fundo')['retorno_junior'].transform(
        lambda x: (1 + pd.to_numeric(x, errors='coerce').fillna(0) / 100).cumprod() - 1
    )
    dataframes['cvm'] = df_cvm

    # Dados Específicos
    df_spec = dataframes['specific_data']
    df_spec['Date'] = pd.to_datetime(df_spec['Date'], errors='coerce', dayfirst=True)
    for col in ['Value', 'Threshold']:
        if col in df_spec.columns:
            df_spec[col] = pd.to_numeric(df_spec[col].astype(str).str.replace(',', '.'), errors='coerce')
    dataframes['specific_data'] = df_spec

    # Dados Macro
    df_macro = dataframes['macro']
    df_macro['Date'] = pd.to_datetime(df_macro['Date'], errors='coerce', dayfirst=True)
    for col in df_macro.columns:
        if col != 'Date':
            df_macro[col] = pd.to_numeric(df_macro[col].astype(str).str.replace(',', '.'), errors='coerce')
    dataframes['macro'] = df_macro

    return dataframes

def style_compliance_table(df_to_style):
    """ Colore a tabela de compliance com base no status. """
    def color_cell(val):
        val_str = str(val).upper()
        if 'FLAG' in val_str: return 'background-color: #ffcccb'
        if 'OK' in val_str: return 'background-color: #90ee90'
        if 'N/A' in val_str: return 'background-color: #d3d3d3'
        return ''
    return df_to_style.style.applymap(color_cell)

# --- Início do Dashboard ---
st.title("📈 Portfolio Monitoring Dashboard")

with st.spinner('Carregando dados... Por favor, aguarde.'):
    all_data = load_all_data(DATA_DIR)

if all_data:
    df_cvm = all_data['cvm']
    df_specific_data = all_data.get('specific_data')
    df_macro = all_data.get('macro')

    # --- Criação das Abas ---
    tab1, tab2, tab3 = st.tabs([" Portfolio Summary ", " Deal by Deal Analysis ", " Macro Analysis "])

    # --- ABA 1: RESUMO DO PORTFÓLIO ---
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
            st.info("Nenhuma coluna de status de covenant da CVM foi encontrada nos dados.")

    # --- ABA 2: ANÁLISE POR FUNDO ---
    with tab2:
        st.sidebar.header("Deal by Deal Filters")
        
        fundos_cvm = df_cvm['fundo'].unique()
        fundos_specific = []
        if df_specific_data is not None:
            fundos_specific = df_specific_data['Deal'].unique()
        
        todos_os_fundos = pd.concat([pd.Series(fundos_cvm), pd.Series(fundos_specific)]).unique()
        fundos_disponiveis = sorted([f for f in todos_os_fundos if pd.notna(f)])
        
        selected_fund = st.sidebar.selectbox('Select a Fund (Deal):', options=fundos_disponiveis, key='deal_selector')
        
        st.header(f"Analysis: {selected_fund}")

        # --- Seção de Dados da CVM ---
        df_fund_cvm = df_cvm[df_cvm['fundo'] == selected_fund].copy()
        if not df_fund_cvm.empty:
            latest_data_cvm = df_fund_cvm.iloc[-1]
            kpi_cols = st.columns(3)
            kpi_cols[0].metric("Net Worth", f"R$ {latest_data_cvm['net_worth']/1e6:,.2f} M")
            kpi_cols[1].metric("PV of Credit Rights", f"R$ {latest_data_cvm['pv_credit_rights']/1e6:,.2f} M")
            kpi_cols[2].metric("PDD", f"R$ {latest_data_cvm['pdd']/1e6:,.2f} M")
            
            st.subheader("CVM Data Analysis")
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
                metrics_to_plot = {}
                sub_cols = [col for col in df_fund_cvm.columns if 'subordination_' in col]
                for sub_col in sub_cols:
                    threshold_col = sub_col.replace('subordination', 'threshold')
                    if threshold_col in df_fund_cvm.columns and df_fund_cvm[threshold_col].notna().any():
                        metrics_to_plot[sub_col] = True
                        metrics_to_plot[threshold_col] = True
                sub_cols_to_plot = list(metrics_to_plot.keys())
                if sub_cols_to_plot:
                    df_melt2 = df_fund_cvm[['data_referencia'] + sub_cols_to_plot].melt(id_vars='data_referencia', value_vars=sub_cols_to_plot, var_name='Metric', value_name='Ratio')
                    df_melt2.dropna(subset=['Ratio'], inplace=True)
                    if not df_melt2.empty:
                        fig2 = px.line(df_melt2, x='data_referencia', y='Ratio', color='Metric', labels={"data_referencia": "Date", "Ratio": "Subordination Ratio"})
                        fig2.update_yaxes(tickformat=".2%")
                        st.plotly_chart(fig2, use_container_width=True)
                    else: st.warning("No CVM subordination data found for this fund.")
                else: st.warning("No CVM subordination metrics with defined thresholds found for this fund.")

            with graph_col1:
                st.subheader("3. Junior Quota Cumulative Return")
                fig3 = px.area(df_fund_cvm, x='data_referencia', y='retorno_junior_acumulado', labels={"data_referencia": "Date", "retorno_junior_acumulado": "Cumulative Return"})
                fig3.update_yaxes(tickformat=".2%")
                st.plotly_chart(fig3, use_container_width=True)

            with graph_col2:
                st.subheader("4. Delinquency by Range (% of PV)")
                delinq_cols = [col for col in df_fund_cvm.columns if col.startswith('delinq_ratio_')]
                if delinq_cols:
                    df_melt4 = df_fund_cvm.melt(id_vars='data_referencia', value_vars=delinq_cols, var_name='Delinquency Bucket', value_name='Percent of PV')
                    fig4 = px.bar(df_melt4, x='data_referencia', y='Percent of PV', color='Delinquency Bucket', barmode='stack')
                    fig4.update_yaxes(tickformat=".2%")
                    st.plotly_chart(fig4, use_container_width=True)
                else: st.warning("No delinquency metrics found for this fund.")

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
                if prazo_cols:
                    df_melt6 = df_fund_cvm.melt(id_vars='data_referencia', value_vars=prazo_cols, var_name='Aging Bucket', value_name='Value (BRL)')
                    fig6 = px.bar(df_melt6, x='data_referencia', y='Value (BRL)', color='Aging Bucket', barmode='stack')
                    st.plotly_chart(fig6, use_container_width=True)
                else: st.warning("No aging metrics found for this fund.")
        else:
            st.info(f"No CVM data available for {selected_fund}.")
        
        st.markdown("---")
        
        # --- Seção de Dados Específicos ---
        st.subheader("Specific Data Analysis")
        if df_specific_data is not None:
            df_fund_spec = df_specific_data[df_specific_data['Deal'] == selected_fund].copy()
            if not df_fund_spec.empty:
                st.markdown("##### Performance Over Time")
                df_fund_spec.dropna(subset=['Date'], inplace=True)
                
                covenant_table = df_fund_spec.pivot_table(index='Date', columns='Metric', values='Value').sort_index(ascending=False)
                status_table = df_fund_spec.pivot_table(index='Date', columns='Metric', values='Status', aggfunc='first').sort_index(ascending=False)
                status_table = status_table.reindex(index=covenant_table.index, columns=covenant_table.columns)
                
                def color_specific_data_cells(data):
                    style_df = pd.DataFrame('', index=data.index, columns=data.columns)
                    for r_idx, row in status_table.iterrows():
                        for c_idx, status_val in row.items():
                            if pd.isna(status_val): continue
                            status_val_upper = str(status_val).upper()
                            if 'FLAG' in status_val_upper: style_df.loc[r_idx, c_idx] = 'background-color: #ffcccb'
                            elif 'OK' in status_val_upper: style_df.loc[r_idx, c_idx] = 'background-color: #90ee90'
                    return style_df
                
                st.dataframe(covenant_table.style.format("{:,.2f}").apply(color_specific_data_cells, axis=None))
                
                st.markdown("##### Graphical Analysis")
                available_metrics = sorted(df_fund_spec['Metric'].unique())
                
                for metric in available_metrics:
                    df_metric_plot = df_fund_spec[df_fund_spec['Metric'] == metric].sort_values(by='Date')
                    if not df_metric_plot.empty:
                        fig_cov = go.Figure()
                        fig_cov.add_trace(go.Scatter(x=df_metric_plot['Date'], y=df_metric_plot['Value'], name='Metric Value', mode='lines+markers'))
                        fig_cov.add_trace(go.Scatter(x=df_metric_plot['Date'], y=df_metric_plot['Threshold'], name='Threshold', mode='lines', line=dict(dash='dot', color='red')))
                        fig_cov.update_layout(title=f"Performance of: {metric}", xaxis_title="Date", yaxis_title="Value")
                        st.plotly_chart(fig_cov, use_container_width=True)
            else:
                st.info(f"No specific data available for {selected_fund}.")
        else:
            st.info("File 'Specific_Data.csv' not loaded.")
        

    # --- ABA 3: ANÁLISE MACRO ---
    with tab3:
        st.header("Macroeconomic Analysis")
        if df_macro is not None:
            # CORREÇÃO: Multiplica as colunas relevantes por 1,000,000 para a escala correta
            cols_to_convert = ['Credit_Portfolio_Total_BRL_mn', 'Credit_Portfolio_Corporate_BRL_mn', 'Credit_Portfolio_Retail_BRL_mn', 'Primary_Result_YTD_ex-FX_BRL_mn']

            df_macro_analysis = df_macro.set_index('Date').sort_index()

            st.subheader("1. Total Credit Portfolio Brazil")
            credit_cols = ['Credit_Portfolio_Total', 'Credit_Portfolio_Corporate', 'Credit_Portfolio_Retail']
            # CORREÇÃO: Remove " (BRL mn)" do título
            fig_credit = px.line(df_macro_analysis, y=credit_cols, title="Credit Portfolio Evolution")
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
                # CORREÇÃO: Remove " (BRL mn)" do título
                fig_primary_result = px.bar(df_macro_analysis, y='Primary_Result_YTD_ex-FX', title="Primary Result YTD")
                st.plotly_chart(fig_primary_result, use_container_width=True)
        else:
            st.info("File 'Macro.csv' not loaded.")
else:
    st.info("Aguardando o carregamento dos dados para exibir o dashboard.")

