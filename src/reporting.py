import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import logging
import os
import dataframe_image as dfi
from . import utils # Certifique-se de que src/reporting.py importa o utils

# --- ESTILO GLOBAL DOS GRÁFICOS ---
plt.style.use('ggplot')


# --- FUNÇÕES AUXILIARES PARA CÁLCULO DE MÉTRICAS ---

def _extract_trades(df_backtest: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Extrai os trades individuais, com a lógica de timing corrigida.
    Lida com entradas, saídas e "flips" (inversão direta).
    """
    logging.info("Extraindo trades individuais...")
    
    positions = df_backtest['actual_position']
    trades = []
    current_trade = {}

    for i in range(1, len(df_backtest)):
        pos_prev = positions.iloc[i - 1]
        pos_curr = positions.iloc[i]

        if pos_curr == pos_prev:
            continue

        is_exit = pos_prev != 0 and pos_curr == 0
        is_entry = pos_prev == 0 and pos_curr != 0
        is_flip = (pos_prev * pos_curr) < 0

        if (is_exit or is_flip) and current_trade:
            # A saída é marcada pelo valor do portfólio no fechamento do candle anterior (i-1)
            exit_candle = df_backtest.iloc[i - 1]
            current_trade['exit_date'] = exit_candle.name
            current_trade['exit_price'] = exit_candle['portfolio_value']
            current_trade['pnl'] = current_trade['exit_price'] - current_trade['entry_price']
            current_trade['return_pct'] = (current_trade['pnl'] / current_trade['entry_price']) * 100 if current_trade['entry_price'] != 0 else 0
            current_trade['duration_bars'] = len(df_backtest.loc[current_trade['entry_date']:current_trade['exit_date']])
            current_trade['status'] = 'Fechada'
            
            trades.append(current_trade)
            current_trade = {}

        if is_entry or is_flip:
            # =============================================================================
            # ### CORREÇÃO FILOSÓFICA APLICADA AQUI ###
            # O capital de entrada ('entry_price') de um trade que começa no candle 'i'
            # é o valor do portfólio no final do candle ANTERIOR ('i-1').
            # =============================================================================
            entry_candle_start = df_backtest.iloc[i - 1]
            entry_candle_end = df_backtest.iloc[i]
            
            current_trade = {
                'entry_date': entry_candle_end.name,
                'entry_price': entry_candle_start['portfolio_value'], # <-- LÓGICA CORRIGIDA
                'position_type': 'Long Spread' if pos_curr == 1 else 'Short Spread',
                'status': 'Aberta'
            }

    if current_trade:
        logging.warning("Um trade terminou em aberto no final do backtest. Analisando resultado não realizado.")
        last_row = df_backtest.iloc[-1]
        current_trade['exit_date'] = last_row.name
        current_trade['exit_price'] = last_row['portfolio_value']
        current_trade['pnl'] = current_trade['exit_price'] - current_trade['entry_price']
        current_trade['return_pct'] = (current_trade['pnl'] / current_trade['entry_price']) * 100 if current_trade['entry_price'] != 0 else 0
        current_trade['duration_bars'] = len(df_backtest.loc[current_trade['entry_date']:current_trade['exit_date']])
        
        trades.append(current_trade)

    if not trades:
        logging.warning("Nenhum trade foi encontrado para extrair.")
        return pd.DataFrame()

    return pd.DataFrame(trades)


def _calculate_overall_metrics(equity_curve: pd.Series, config: dict) -> dict:
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100
    num_years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
    cagr = ((equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1 / num_years) - 1) * 100 if num_years > 0 else 0
    candles_per_day = config['candles_per_day']
    daily_returns = equity_curve.pct_change()
    annual_volatility = daily_returns.std() * np.sqrt(252 * candles_per_day)
    risk_free_rate_annual = 0.10
    sharpe_ratio = (cagr/100 - risk_free_rate_annual) / annual_volatility if annual_volatility != 0 else 0
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_drawdown = drawdown.min() * 100

    return {
        "Retorno Total (%)": total_return,
        "CAGR (%)": cagr,
        "Volatilidade Anualizada (%)": annual_volatility * 100,
        "Índice de Sharpe": sharpe_ratio,
        "Máximo Drawdown (%)": max_drawdown
    }


def _calculate_trade_stats(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame()

    long_trades = trades_df[trades_df['position_type'] == 'Long Spread']
    short_trades = trades_df[trades_df['position_type'] == 'Short Spread']
    
    stats = {}
    
    for name, df_group in [('Total', trades_df), ('Long Spread', long_trades), ('Short Spread', short_trades)]:
        if df_group.empty:
            continue
   
        # --- CORREÇÃO ---
        # 1. Cria uma cópia limpa do grupo, removendo trades com retorno NaN
        df_group_clean = df_group.dropna(subset=['return_pct'])
        
        # 2. Usa a cópia limpa para fazer a máscara
        wins = df_group_clean[df_group_clean['return_pct'] > 0]
        losses = df_group_clean[df_group_clean['return_pct'] <= 0]

        # 3. Continua usando df_group_clean para os cálculos subsequentes
        gross_profit = wins['pnl'].sum()
        gross_loss = abs(losses['pnl'].sum())
        
        # (Use df_group_clean para os outros cálculos também)
        num_trades_clean = len(df_group_clean)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        payoff_ratio = (wins['return_pct'].mean() / abs(losses['return_pct'].mean())) if not losses.empty and losses['return_pct'].abs().mean() > 0 else float('inf')

        stats[name] = {
            'Nº de Trades': num_trades_clean, # Usa o número de trades válidos
            'Taxa de Acerto (%)': (len(wins) / num_trades_clean * 100) if num_trades_clean > 0 else 0,
            'Profit Factor': profit_factor,
            'Payoff Ratio': payoff_ratio,
            'Retorno Médio (%)': df_group_clean['return_pct'].mean(), # Usa os retornos válidos
            'Melhor Trade (%)': df_group_clean['return_pct'].max(),
            'Pior Trade (%)': df_group_clean['return_pct'].min(),
        }
        
    return pd.DataFrame(stats).T.fillna(0)


def _save_table_as_csv(df: pd.DataFrame, title: str, filepath: str):
    """
    Salva um DataFrame diretamente em um arquivo CSV.
    """
    # Garante que o diretório exista
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Define o nome do arquivo com a extensão .csv
    filepath_csv = filepath.replace('.png', '.csv') 
    
    logging.info(f"Salvando tabela '{title}' em: {filepath_csv}")
    try:
        # Salva o DataFrame em CSV com formatação razoável
        df.to_csv(filepath_csv, float_format='%.4f') 
        logging.info(f"SUCESSO: Tabela '{title}' salva como CSV.")
    except Exception as e:
        logging.error(f"Erro ao salvar tabela '{title}' como CSV: {e}")


# --- FUNÇÕES DE PLOTAGEM ---

def plot_dynamic_indicators(df_strategy: pd.DataFrame, config: dict, output_path: str):
    logging.info("Gerando gráficos dos indicadores dinâmicos...")
    pair_name = f"{config['pair_to_backtest'][0]}_{config['pair_to_backtest'][1]}"
    filepath = os.path.join(output_path, f"indicadores_dinamicos_{pair_name}.png")
    fig, axs = plt.subplots(3, 1, figsize=(15, 12), sharex=True)
    fig.suptitle(f'Indicadores Dinâmicos para o Par: {pair_name}', fontsize=16)
    axs[0].plot(df_strategy.index, df_strategy['hedge_ratio'], label='Hedge Ratio Dinâmico')
    axs[0].set_title('Hedge Ratio (Walk-Forward)')
    axs[0].legend()
    axs[1].plot(df_strategy.index, df_strategy['spread'], label='Spread')
    axs[1].plot(df_strategy.index, df_strategy['spread_mean'], label='Média Móvel do Spread', linestyle='--')
    axs[1].set_title('Spread do Par e sua Média Móvel')
    axs[1].legend()
    axs[2].plot(df_strategy.index, df_strategy['z_score'], label='Z-Score')
    axs[2].set_title('Z-Score do Spread')
    axs[2].legend()
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    logging.info(f"Salvando gráfico de indicadores em: {filepath}")
    fig.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close(fig)

def get_annual_return(series):
    return (series.iloc[-1] / series.iloc[0] - 1) * 100

def plot_equity_curves(strategy_equity: pd.Series, benchmarks: dict, config: dict, output_path: str):
    logging.info("Gerando gráfico comparativo das curvas de capital...")
    pair_name = f"{config['pair_to_backtest'][0]}_{config['pair_to_backtest'][1]}"
    filepath = os.path.join(output_path, f"curva_de_capital_comparativa_{pair_name}.png")
    fig, ax = plt.subplots(figsize=(15, 8))
    ax.plot(strategy_equity.index, strategy_equity, label='Estratégia Z-Score', linewidth=2)
    for name, equity_curve in benchmarks.items():
        ax.plot(equity_curve.index, equity_curve, label=name, linestyle='--')
    ax.set_title(f'Curva de Capital: Estratégia vs. Benchmarks para {pair_name}', fontsize=16)
    ax.set_xlabel('Data')
    ax.set_ylabel('Valor do Portfólio (R$)')
    ax.legend(loc='upper left')
    from matplotlib.ticker import FuncFormatter
    formatter = FuncFormatter(lambda x, p: f'R$ {x:,.0f}'.replace(',', '.'))
    ax.yaxis.set_major_formatter(formatter)
    logging.info(f"Salvando gráfico da curva de capital em: {filepath}")
    fig.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close(fig)

# --- FUNÇÃO PRINCIPAL DE RELATÓRIO ---

def generate_full_report(
    strategy_equity: pd.Series,
    benchmarks: dict,
    df_backtest: pd.DataFrame,
    df_strategy: pd.DataFrame,
    config: dict
):
    pair_name = f"{config['pair_to_backtest'][0]}_{config['pair_to_backtest'][1]}"
    report_path = os.path.join(os.getcwd(), 'reports', pair_name)
    os.makedirs(report_path, exist_ok=True)
    logging.info(f"Todos os relatórios serão salvos em: {report_path}")

    print("\n" + "="*80); print(f"--- RELATÓRIO DE PERFORMANCE: {pair_name} ---"); print("="*80)

    # --- Cálculo dos Retornos ---
    all_equities = pd.DataFrame({'Estratégia Híbrida': strategy_equity}) # <-- Corrigido o nome aqui
    for name, series in benchmarks.items():
        all_equities[name] = series
    all_equities = all_equities.ffill().dropna()

    annual_returns = all_equities.groupby(all_equities.index.year).apply(get_annual_return)
    num_years = (all_equities.index[-1] - all_equities.index[0]).days / 365.25
    cagr = ((all_equities.iloc[-1] / all_equities.iloc[0]) ** (1/num_years) - 1) * 100 if num_years > 0 else pd.Series(0.0, index=all_equities.columns)

    report_returns = annual_returns.T; report_returns['CAGR'] = cagr
    print("\n\n--- Tabela 1: Comparativo de Retorno Anual (%) ---\n")
    # --- CORREÇÃO AQUI ---
    # Limpa NaNs e Infs ANTES de imprimir/salvar
    report_returns_clean = report_returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    print(report_returns_clean.to_string(float_format="%.2f%%"))


    _save_table_as_csv( # <-- Chamada nova
        report_returns_clean, 
        title=f"Comparativo de Retorno Anual (%) - {pair_name}",
        filepath=os.path.join(report_path, "tabela_retornos_anuais.csv") # <-- Nome novo (.csv)
    )
    logging.info("SUCESSO: Tabela de retornos salva como CSV.")

    # --- Cálculo da Volatilidade ---
    daily_returns = all_equities.pct_change()
    candles_per_day = config.get('candles_per_day', 1) # Pega do config atualizado
    annual_volatility = daily_returns.resample('YE').apply(lambda x: x.std() * np.sqrt(252 * candles_per_day)) * 100
    annual_volatility.index = annual_volatility.index.year

    report_vol = annual_volatility.T; report_vol['Média'] = report_vol.mean(axis=1)
    print("\n\n--- Tabela 2: Comparativo de Volatilidade Anualizada (%) ---\n")
    report_vol_clean = report_vol.replace([np.inf, -np.inf], np.nan).fillna(0.0) # <-- Limpa inf E NaN
    print(report_vol_clean.to_string(float_format="%.2f%%"))


    logging.info("Tentando salvar a tabela de volatilidade...")
    _save_table_as_csv( # <-- Chamada nova
        report_vol_clean, 
        title=f"Comparativo de Volatilidade Anualizada (%) - {pair_name}",
        filepath=os.path.join(report_path, "tabela_volatilidade_anual.csv") # <-- Nome novo (.csv)
    )
    
    logging.info("SUCESSO: Tabela de volatilidade salva como csv.")


    # --- O RESTO DO RELATÓRIO CONTINUA ---
    print("\n\n--- Tabela 3: Métricas de Performance da Estratégia Híbrida ---\n") # <-- Corrigido nome
    metrics = _calculate_overall_metrics(strategy_equity, config)
    metrics_df = pd.DataFrame.from_dict(metrics, orient='index', columns=['Valor'])
    print(metrics_df.to_string(float_format="%.2f"))

    print("\n\n--- Tabela 4: Análise de Trades Individuais (Decomposta) ---\n")
    trades_df = _extract_trades(df_backtest, config)

    if not trades_df.empty:
        # Aplica a limpeza de NaNs que fizemos antes
        decomposed_stats_df = _calculate_trade_stats(trades_df)
        if not decomposed_stats_df.empty:
            print(decomposed_stats_df.to_string(float_format="%.2f"))
        else:
            print("Nenhuma estatística de trade pôde ser calculada.")
    else:
        print("Nenhum trade foi executado para análise.")

    print("\n" + "="*80); print("--- FIM DO RELATÓRIO ---"); print("="*80 + "\n")

    # --- Plotagem dos Gráficos ---
    try:
        plot_dynamic_indicators(df_strategy, config, output_path=report_path)
    except Exception as e:
        logging.error(f"Erro ao plotar indicadores dinâmicos: {e}")

    try:
        plot_equity_curves(strategy_equity, benchmarks, config, output_path=report_path)
    except Exception as e:
        logging.error(f"Erro ao plotar curvas de capital: {e}")

def print_validation_summary(df_valid_pairs: pd.DataFrame):
    """
    Imprime um resumo formatado dos pares aprovados para backtest.
    (Lógica movida de main_pipeline.py)
    """
    if df_valid_pairs.empty:
        logging.warning("Nenhum par cointegrado encontrado com os critérios definidos. Encerrando pipeline.")
        return

    logging.info(f"Encontrados {len(df_valid_pairs)} pares aprovados para backtest:")
    
    # Recria a lógica de formatação que estava no main_pipeline.py
    df_print = df_valid_pairs.copy()
    
    # Tenta usar a função formatar_meia_vida que movemos para utils
    if 'half_life_minutes' in df_print.columns:
        df_print['meia_vida'] = df_print['half_life_minutes'].apply(utils.formatar_meia_vida)
    
    if 'relationship' in df_print.columns:
        df_print['relationship_str'] = df_print['relationship'].apply(lambda x: '_'.join(x))
    
    colunas_para_mostrar = [
        'relationship_str', 'status',
        'adf_p_value_Y', 'adf_p_value_X',
        'coint_p_value', 'kpss_p_value', 
        'hurst_exponent', 'is_stationary_robust', 'meia_vida'
    ]
    
    # Filtra colunas que podem não existir (ex: 'meia_vida')
    colunas_finais = [col for col in colunas_para_mostrar if col in df_print.columns]
    
    # Imprime a tabela formatada
    print(df_print[colunas_finais].to_string(index=False, float_format='%.4f'))