import os
import logging
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5
import yfinance as yf
from dotenv import load_dotenv
from bcb import sgs as bcb

# --- CONFIGURAÇÃO INICIAL ---
# Configura o logging para dar feedback sobre o processo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mapeamento de strings para os timeframes do MT5
TIMEFRAME_MAP_MT5 = {  # <--- RENOMEAR MAPA
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "D1": mt5.TIMEFRAME_D1,
}

# --- NOVO MAPA PARA YFINANCE ---
TIMEFRAME_MAP_YF = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",  # YFinance aceita "60m" ou "1h"
    "D1": "1d",
}

def connect_to_mt5():
    """
    Carrega as credenciais do arquivo .env e inicializa a conexão com o MT5.
    """
    load_dotenv() # Carrega as variáveis do arquivo .env

    login = int(os.getenv("MT5_LOGIN"))
    password = str(os.getenv("MT5_PASSWORD"))
    server = str(os.getenv("MT5_SERVER"))

    if not mt5.initialize(login=login, password=password, server=server):
        logging.error(f"Falha na inicialização do MT5, erro code = {mt5.last_error()}")
        return False
    
    logging.info("Conexão com o MetaTrader 5 estabelecida com sucesso.")
    return True

def fetch_data_mt5(tickers: list, start_date: datetime, end_date: datetime, timeframe_str: str) -> dict:
    """
    Busca dados históricos para uma lista de tickers do MetaTrader 5.

    Args:
        tickers (list): Uma lista de strings com os nomes dos ativos.
        start_date (datetime): A data de início da coleta.
        end_date (datetime): A data de fim da coleta.
        timeframe_str (str): O timeframe desejado (ex: "M1", "H1", "D1").

    Returns:
        dict: Um dicionário onde as chaves são os tickers e os valores são os DataFrames com os dados.
    """
    if not connect_to_mt5():
        return {} # Retorna um dicionário vazio se a conexão falhar

    # Valida o timeframe passado como argumento
    timeframe = TIMEFRAME_MAP_MT5.get(timeframe_str.upper()) # <--- USA O MAPA MT5
    if timeframe is None:
        logging.error(f"Timeframe '{timeframe_str}' inválido para MT5. Válidos: {list(TIMEFRAME_MAP_MT5.keys())}")
        mt5.shutdown()
        return {}

    all_data = {}
    logging.info(f"Iniciando busca de dados MT5 para {len(tickers)} ativos...")

    try:
        for ticker in tickers:
            logging.info(f"Buscando dados para: {ticker}")
            
            candles = mt5.copy_rates_range(
                ticker,
                timeframe,
                start_date,
                end_date
            )
            
            if candles is None or len(candles) == 0:
                logging.warning(f" -> Nenhum dado encontrado para {ticker} no período solicitado.")
                continue

            df = pd.DataFrame(candles)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            all_data[ticker] = df
            logging.info(f" -> {len(df)} candles carregados para {ticker}.")

    finally:
        # Garante que a conexão seja sempre encerrada, mesmo que ocorra um erro.
        logging.info("Encerrando conexão com o MetaTrader 5.")
        mt5.shutdown()

    logging.info(f"\nProcesso de coleta concluído. Total de ativos carregados: {len(all_data)}.")
    return all_data

# --- FUNÇÃO TOTALMENTE NOVA ---
def fetch_data_yfinance(tickers: list, start_date: datetime, end_date: datetime, timeframe_str: str) -> dict:
    """
    Busca dados históricos para uma lista de tickers do Yahoo Finance
    e formata o DataFrame para ser IDÊNTICO ao do MT5.
    """
    interval = TIMEFRAME_MAP_YF.get(timeframe_str.upper())
    if interval is None:
        logging.error(f"Timeframe '{timeframe_str}' inválido para YFinance. Válidos: {list(TIMEFRAME_MAP_YF.keys())}")
        return {}

    all_data = {}
    logging.info(f"Iniciando busca de dados YFinance para {len(tickers)} ativos...")

    # yfinance usa strings, não datetime objects, para start/end
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    for ticker in tickers:
        logging.info(f"Buscando dados para: {ticker} (YFinance)")
        try:
            df = yf.download(
                ticker,
                start=start_str,
                end=end_str,
                interval=interval,
                progress=False,
                auto_adjust=False  # Crucial! Queremos o 'Adj Close' separado
            )
            
            if df.empty:
                logging.warning(f" -> Nenhum dado encontrado para {ticker} (YFinance).")
                continue

            # --- ALINHAMENTO DE SCHEMA (A PARTE MAIS IMPORTANTE) ---
            
            # 1. Usar 'Adj Close' como nosso 'close' (assim como no Repo 1)
            df['close'] = df['Adj Close']
            
            # 2. Renomear colunas do YFinance (Maiúsculas) para o padrão MT5 (minúsculas)
            df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Volume': 'real_volume' # 'Volume' do YF é o volume real
            }, inplace=True)

            # 3. Adicionar colunas que existem no MT5 mas não no YFinance
            df['tick_volume'] = df['real_volume'] # Melhor aproximação
            df['spread'] = 0 # YFinance não fornece spread de candle

            # 4. Selecionar e reordenar as colunas para o padrão final
            # O 'processing.py' só usa 'close', mas fazemos isso 
            # para manter o padrão e a prova de futuro.
            mt5_columns = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
            df_final = df[mt5_columns]
            
            all_data[ticker] = df_final
            logging.info(f" -> {len(df_final)} candles carregados para {ticker} (YFinance).")

        except Exception as e:
            logging.warning(f" -> Falha ao baixar {ticker} (YFinance): {e}")

    logging.info(f"\nProcesso de coleta YFinance concluído. Total: {len(all_data)}.")
    return all_data

def save_data_to_parquet(data_dict: dict, path: str):
    """
    Salva cada DataFrame de um dicionário em um arquivo Parquet separado.

    Args:
        data_dict (dict): Dicionário de DataFrames (saída de fetch_data_mt5).
        path (str): Caminho para a pasta onde os arquivos serão salvos (ex: 'data/raw/').
    """
    if not os.path.exists(path):
        os.makedirs(path)
        logging.info(f"Diretório criado: {path}")

    for ticker, df in data_dict.items():
        file_path = os.path.join(path, f"{ticker}.parquet")
        df.to_parquet(file_path)
        logging.info(f"Dados de {ticker} salvos em: {file_path}")

def fetch_cdi_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Busca a série histórica da taxa DI (CDI) diária do SGS do Banco Central.
    Código da série: 12.
    Lida com períodos longos (>10 anos) fazendo buscas anuais em lote.

    Args:
        start_date (datetime): Data de início da busca.
        end_date (datetime): Data de fim da busca.

    Returns:
        pd.DataFrame: DataFrame com as datas como índice e a taxa CDI em formato decimal.
    """
    logging.info("Iniciando busca de dados do CDI no Banco Central...")
    
    all_cdi_data = []

    # <-- LÓGICA DE LOOP REINSERIDA -->
    # Se o período for maior que 10 anos, busca ano a ano
    if (end_date - start_date).days > 3650:
        logging.warning("Período maior que 10 anos. A busca do CDI será feita em lotes anuais.")
        for year in range(start_date.year, end_date.year + 1):
            year_start = datetime(year, 1, 1).strftime('%Y-%m-%d')
            year_end = datetime(year, 12, 31).strftime('%Y-%m-%d')
            logging.info(f"Buscando CDI para o ano de {year}...")
            try:
                df_year = bcb.get({'valor':12}, start=year_start, end=year_end)
                all_cdi_data.append(df_year)
            except ValueError:
                logging.warning(f"Nenhum dado de CDI encontrado para o ano {year}.")
                continue
        
        if not all_cdi_data:
            return None
        df_cdi = pd.concat(all_cdi_data)

    else: # Se for menor, busca o período completo de uma vez
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        try:
            df_cdi = bcb.get({'valor':12}, start=start_date_str, end=end_date_str)
        except ValueError:
            logging.error("Não foi possível buscar os dados do CDI. Verifique o período e a conexão.")
            return None

    if df_cdi.empty:
        logging.warning("Nenhum dado de CDI retornado para o período solicitado.")
        return None

    # Processamento final (comum a ambos os casos)
    df_cdi['valor'] = df_cdi['valor'] / 100.0
    df_cdi['Date'] = df_cdi.index

    df_cdi = df_cdi.rename(columns={'Date': 'date', 'valor': 'cdi_rate'})
    df_cdi['date'] = pd.to_datetime(df_cdi['date'], dayfirst=True)
    df_cdi.drop_duplicates(subset=['date'], inplace=True) # Garante que não haja datas duplicadas do concat
    df_cdi = df_cdi.set_index('date')
    
    logging.info(f" -> {len(df_cdi)} registros de CDI carregados com sucesso.")
    return df_cdi
