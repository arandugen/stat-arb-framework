import os
import sys
import argparse
import pandas as pd
import numpy as np
import logging
from pathlib import Path

# --- CONFIGURAÇÃO DE AMBIENTE E PATHS ---
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# --- IMPORTAÇÃO DOS NOSSOS MÓDULOS ---
import config
from src import strategy, backtesting, benchmarks, reporting, utils

# --- CONFIGURAÇÃO DO LOGGING ---
# (Já é configurado no main.py, mas mantido para execução independente)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')


def main_backtest(pair_to_backtest: tuple):
    """
    Orquestra a execução de um backtest completo e a análise de performance para um par de ativos.
    """
    pair_name = '_'.join(pair_to_backtest)
    logging.info(f"--- INICIANDO BACKTEST E ANÁLISE PARA O PAR: {pair_name} ---")

    # --- 1. CARREGAMENTO DE DADOS ---
    processed_data_path = project_root / "data" / "processed"
    raw_data_path = project_root / "data" / "raw"

    # a) Carrega dados do par (preços em log)
    pair_log_prices_path = processed_data_path / f"{pair_name}_log_prices.parquet"
    try:
        df_log_prices = pd.read_parquet(pair_log_prices_path)
        df_prices = np.exp(df_log_prices)
        logging.info(f"Dados do par {pair_name} carregados com sucesso.")
    except FileNotFoundError:
        logging.error(f"Arquivo de dados processados não encontrado: {pair_log_prices_path}")
        return

    # b) Carrega dados dos benchmarks (CDI)
    try:
        df_cdi = pd.read_parquet(raw_data_path / "CDI.parquet")
        logging.info("Dados de benchmark (CDI) carregados com sucesso.")
    except FileNotFoundError as e:
        logging.error(f"Arquivo de dados brutos para benchmark não encontrado: {e}")
        return

    # --- 2. PREPARAÇÃO DA CONFIGURAÇÃO ---
    backtest_config = config.BACKTEST_CONFIG.copy()
    backtest_config["pair_to_backtest"] = pair_to_backtest
    backtest_config["formation_window"] = utils.calculate_formation_window(
        backtest_config, 
        config.timeframe
    )

    # --- 3. EXECUÇÃO DA ESTRATÉGIA (Cálculo de Sinais) ---
    df_strategy = strategy.calculate_dynamic_zscore(df_log_prices, backtest_config)
    
    # --- PROTEÇÃO ---
    if df_strategy is None or df_strategy.empty:
        logging.warning(f"⚠️ Estratégia inválida ou vazia para {pair_name}. Pulando backtest.")
        return None  # Retorna explicitamente None para o orquestrador entender
    
    df_with_signals = strategy.generate_hybrid_signals(
        df_strategy, 
        config.STRATEGY_CONFIG # Passa o novo "Painel de Controle"
    )
    
    df_signals_only = df_with_signals.drop(columns=list(pair_to_backtest))
    
    df_ready_for_backtest = df_prices.join(df_signals_only, how='inner')

    # --- JUNTA O CDI AO DATAFRAME PRINCIPAL ---
    logging.info("Alinhando e juntando dados do CDI para o backtest de caixa...")
    
    cdi_aligned = df_cdi.reindex(df_ready_for_backtest.index, method='ffill')
    
    candles_per_day = backtest_config.get('candles_per_day', 1)
    if candles_per_day > 0:
    
        cdi_aligned['cdi_rate'] = cdi_aligned['cdi_rate'] / candles_per_day
    else:
        cdi_aligned['cdi_rate'] = 0.0 # Segurança
        
    df_ready_for_backtest = df_ready_for_backtest.join(cdi_aligned['cdi_rate']).fillna(0.0)

    # --- 4. EXECUÇÃO DO BACKTEST PRINCIPAL ---
    df_results = backtesting.run_backtest(df_ready_for_backtest, backtest_config)
    strategy_equity = df_results['portfolio_value']

    # --- 5. CÁLCULO DOS BENCHMARKS ---
    benchmarks_data = {}
    
    benchmarks_data['Hedge Dinâmico'] = benchmarks.calculate_dynamic_hedge_benchmark(
        df_prices, df_strategy['hedge_ratio'], backtest_config
    )
    benchmarks_data[f'Buy & Hold {pair_to_backtest[0]}'] = benchmarks.calculate_buy_and_hold_benchmark(
        df_prices, pair_to_backtest[0], backtest_config
    )
    benchmarks_data[f'Buy & Hold {pair_to_backtest[1]}'] = benchmarks.calculate_buy_and_hold_benchmark(
        df_prices, pair_to_backtest[1], backtest_config
    )
    benchmarks_data['CDI'] = benchmarks.calculate_risk_free_benchmark(
        df_results.index, df_cdi, backtest_config
    )
    
    # --- 6. GERAÇÃO DO RELATÓRIO CONSOLIDADO ---
    reporting.generate_full_report(
        strategy_equity=strategy_equity,
        benchmarks=benchmarks_data,
        df_backtest=df_results,
        df_strategy=df_strategy,
        config=backtest_config
    )
    
    logging.info(f"--- ANÁLISE CONCLUÍDA PARA O PAR: {pair_name} ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Executa o backtest completo e a análise de performance para um par de ativos."
    )
    parser.add_argument(
        '--pair', 
        nargs=2, 
        metavar=('ATIVO_Y', 'ATIVO_X'), 
        required=True,
        help="O par de tickers para executar o backtest (ex: --pair SUZB3 KLBN11)"
    )
    args = parser.parse_args()
    
    main_backtest(tuple(args.pair))