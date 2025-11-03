import os
import sys
import argparse
import logging

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src import data_collection, processing, utils
import config

def get_all_assets_from_config():
    """
    Lê o config.py (arquitetura mista) e retorna:
    1. Um set de tickers para baixar do MT5.
    2. Um set de tickers para baixar do YFinance.
    3. Uma lista de tuplas de pares (só os nomes) para o processing.py.
    """
    mt5_tickers = set()
    yf_tickers = set()
    pairs_for_processing = []
    
    all_assets_with_source = []
    
    # 1. Coleta tickers dos Pares
    for (y_asset, x_asset) in config.ASSET_PAIRS_TO_ANALYZE:
        y_ticker, y_source = y_asset
        x_ticker, x_source = x_asset
        
        all_assets_with_source.append(y_asset)
        all_assets_with_source.append(x_asset)
        
        pairs_for_processing.append((y_ticker, x_ticker))
        
    # 2. Coleta tickers dos Benchmarks
    for (ticker, source) in config.BENCHMARK_TICKERS:
        all_assets_with_source.append((ticker, source))

    # 3. Separa os tickers únicos por fonte
    for (ticker, source) in all_assets_with_source:
        if source == 'mt5':
            mt5_tickers.add(ticker)
        elif source == 'yfinance':
            yf_tickers.add(ticker)
        else:
            logging.warning(f"Fonte '{source}' desconhecida para o ticker '{ticker}'. Pulando.")
            
    return list(mt5_tickers), list(yf_tickers), pairs_for_processing

def download_all_data(clean_dir: bool = False):
    """
    Orquestra o download de dados de FONTES MISTAS (MT5 e YFinance) e CDI.
    """
    logging.info("--- INICIANDO ETAPA 1: COLETA DE DADOS (FONTES MISTAS) ---")
    raw_data_path = os.path.join(project_root, 'data', 'raw')
    if clean_dir:
        utils.clean_directory(raw_data_path)

    # 1. Pega as listas de download separadas por fonte
    mt5_tickers_to_download, yf_tickers_to_download, _ = get_all_assets_from_config()

    all_raw_data = {}

    # 2. Coleta do MT5
    if mt5_tickers_to_download:
        logging.info(f"Coletando {len(mt5_tickers_to_download)} tickers do MT5...")
        raw_data_mt5 = data_collection.fetch_data_mt5(
            tickers=mt5_tickers_to_download,
            start_date=config.data_inicio,
            end_date=config.data_fim,
            timeframe_str=config.timeframe
        )
        all_raw_data.update(raw_data_mt5)
    else:
        logging.info("Nenhum ticker configurado para coleta via MT5.")

    # 3. Coleta do YFinance
    if yf_tickers_to_download:
        logging.info(f"Coletando {len(yf_tickers_to_download)} tickers do YFinance...")
        raw_data_yf = data_collection.fetch_data_yfinance(
            tickers=yf_tickers_to_download,
            start_date=config.data_inicio,
            end_date=config.data_fim,
            timeframe_str=config.timeframe
        )
        all_raw_data.update(raw_data_yf)
    else:
        logging.info("Nenhum ticker configurado para coleta via YFinance.")
    
    # 4. Salva dados dos ativos
    if all_raw_data:
        logging.info(f"Salvando dados de {len(all_raw_data)} ativos no total...")
        data_collection.save_data_to_parquet(all_raw_data, raw_data_path)
    else:
        logging.warning("Nenhum dado de ativo foi baixado.")
        
    # 5. Dados do CDI
    df_cdi = data_collection.fetch_cdi_data(config.data_inicio, config.data_fim)
    if df_cdi is not None and not df_cdi.empty:
        df_cdi.to_parquet(os.path.join(raw_data_path, "CDI.parquet"))
        logging.info("Dados de CDI salvos com sucesso.")

def process_all_data(clean_dir: bool = False):
    """Orquestra o processamento dos dados brutos."""
    logging.info("--- INICIANDO ETAPA 2: PROCESSAMENTO ---")
    raw_data_path = os.path.join(project_root, 'data', 'raw')
    processed_data_path = os.path.join(project_root, 'data', 'processed')

    if clean_dir:
        utils.clean_directory(processed_data_path)
    
    _, _, pairs_to_process = get_all_assets_from_config()

    if not pairs_to_process:
        logging.error("Nenhuma lista de pares encontrada para processar.")
        return

    processing.process_and_save_relationships(
        relationships_to_process=pairs_to_process,
        raw_path=raw_data_path,
        processed_path=processed_data_path
    )

def main_cli():
    """Função para execução via linha de comando (CLI)."""
    parser = argparse.ArgumentParser(description="Painel de controle para o pipeline de dados do projeto.")
   
    subparsers = parser.add_subparsers(dest='command', required=True, help='Comando a ser executado')
    parser_download = subparsers.add_parser('download', help='Baixa os dados brutos.')
    parser_download.add_argument('--clean', action='store_true')
    parser_process = subparsers.add_parser('process', help='Processa os dados brutos.')
    parser_process.add_argument('--clean', action='store_true')
    args = parser.parse_args()

    if args.command == 'download':
        download_all_data(clean_dir=args.clean)
    elif args.command == 'process':
        process_all_data(clean_dir=args.clean)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main_cli()