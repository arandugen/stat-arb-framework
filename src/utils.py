import os
import glob
import logging
import time
import numpy as np
import re
import pandas as pd

def clean_directory(directory_path: str):
    """
    Exclui todos os arquivos dentro de um diretório especificado.

    Args:
        directory_path (str): O caminho para o diretório a ser limpo.
    """
    logging.info(f"Iniciando limpeza do diretório: {directory_path}")
    if not os.path.exists(directory_path):
        logging.warning(f"Diretório não existe, nada a ser feito: {directory_path}")
        return

    # Usamos glob para encontrar todos os arquivos no diretório
    files_to_delete = glob.glob(os.path.join(directory_path, '*'))
    
    if not files_to_delete:
        logging.info("Diretório já está vazio.")
        return

    deleted_count = 0
    for file_path in files_to_delete:
        try:
            # Garante que estamos excluindo apenas arquivos, e não subdiretórios
            if os.path.isfile(file_path):
                os.unlink(file_path)
                deleted_count += 1
        except Exception as e:
            logging.error(f"Erro ao excluir o arquivo {file_path}: {e}")
    
    logging.info(f"Limpeza concluída. Total de {deleted_count} arquivos excluídos.")

# Configuração básica de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# -------------------------------
# Decorators e logging
# -------------------------------
def timer(func):
    """Mede o tempo de execução de uma função."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        logging.info(f"{func.__name__} executado em {time.time() - start:.2f}s")
        return result
    return wrapper

# -------------------------------
# Salvamento de resultados
# -------------------------------
def save_results(df: pd.DataFrame, filename="results.csv", folder="results") -> str:
    """Salva DataFrame em CSV dentro da pasta results/."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    df.to_csv(path, index=False)
    logging.info(f"Resultados salvos em {path}")
    return path

# -------------------------------
# Métricas de performance
# -------------------------------
def sharpe_ratio(returns: pd.Series, risk_free=0.0) -> float:
    """Calcula o Sharpe Ratio da série de retornos, com proteção para desvio padrão zero."""
    excess_returns = returns - risk_free
    std_dev = np.std(excess_returns, ddof=1)
    
    # Se não houver volatilidade, o Sharpe Ratio é 0.
    if std_dev == 0:
        return 0.0
        
    return np.mean(excess_returns) / std_dev

def max_drawdown(equity_curve: pd.Series) -> float:
    """Calcula o máximo drawdown de uma curva de capital."""
    cum_max = equity_curve.cummax()
    drawdown = (equity_curve - cum_max) / cum_max
    return drawdown.min()

def calculate_time_parameters(timeframe_str: str, trading_hours_per_day: int) -> dict:
    """
    Analisa a string de timeframe (ex: "M30", "H1", "D1") e
    calcula os minutos e candles por dia.
    """
    timeframe_str = timeframe_str.upper()
    trading_minutes_per_day = trading_hours_per_day * 60
    
    freq_in_minutes = 0
    candles_per_day = 0

    if timeframe_str == "D1":
        freq_in_minutes = trading_minutes_per_day
        candles_per_day = 1
        
    elif 'H' in timeframe_str:
        try:
            hours = int(re.findall(r'\d+', timeframe_str)[0])
            freq_in_minutes = hours * 60
            candles_per_day = trading_minutes_per_day / freq_in_minutes
        except Exception:
            raise ValueError(f"Timeframe de Hora inválido: {timeframe_str}")
            
    elif 'M' in timeframe_str:
        try:
            minutes = int(re.findall(r'\d+', timeframe_str)[0])
            freq_in_minutes = minutes
            candles_per_day = trading_minutes_per_day / freq_in_minutes
        except Exception:
            raise ValueError(f"Timeframe de Minuto inválido: {timeframe_str}")
            
    else:
        raise ValueError(f"Timeframe não suportado: {timeframe_str}")

    # Garante que candles_per_day seja um inteiro
    if candles_per_day != int(candles_per_day):
        logging.warning(f"Combinação de timeframe ({timeframe_str}) e horas de pregão ({trading_hours_per_day}) resulta em candles fracionados. Arredondando.")
        candles_per_day = int(round(candles_per_day))

    return {
        "freq_in_minutes": freq_in_minutes,
        "candles_per_day": int(candles_per_day)
    }


def calculate_formation_window(backtest_config: dict, timeframe_str: str) -> int:
    """
    Calcula o tamanho da janela de formação em número de candles,
    derivando os parâmetros de tempo a partir do timeframe_str.
    Também atualiza o dicionário backtest_config com os valores calculados.
    """
    try:
        # 1. Pega os parâmetros base
        formation_months = backtest_config["formation_months"]
        trading_days_per_month = backtest_config["trading_days_per_month"]
        trading_hours_per_day = backtest_config.get("trading_hours_per_day", 8) # Default 8h

        # 2. Calcula os parâmetros de tempo
        time_params = calculate_time_parameters(timeframe_str, trading_hours_per_day)
        
        # 3. Atualiza o config para o resto do pipeline
        backtest_config.update(time_params) # Insere 'freq_in_minutes' e 'candles_per_day'
        
        # 4. A lógica principal do cálculo da janela
        window_size = int(
            formation_months * trading_days_per_month * time_params["candles_per_day"]
        )
        
        logging.info(f"Janela de formação calculada: {window_size} candles ({formation_months} meses).")
        logging.info(f" -> Parâmetros Derivados: {time_params['candles_per_day']} candles/dia, {time_params['freq_in_minutes']} min/candle")
        return window_size

    except KeyError as e:
        logging.error(f"Erro ao calcular janela: Chave ausente no BACKTEST_CONFIG: {e}")
        raise
    except Exception as e:
        logging.error(f"Erro inesperado ao calcular janela de formação: {e}")
        raise