import pandas as pd
import numpy as np
import statsmodels.api as sm
from tqdm import tqdm
import logging
pd.set_option('future.no_silent_downcasting', True)

from . import indicators
from . import models

def calculate_dynamic_zscore(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Calcula os parâmetros dinâmicos (hedge ratio, média e desvio do spread)
    usando uma janela móvel (walk-forward), com base na Célula 2 do notebook.

    Args:
        df (pd.DataFrame): O DataFrame de preços logarítmicos do par.
        config (dict): O dicionário de configuração do backtest.

    Returns:
        pd.DataFrame: Um novo DataFrame contendo os preços originais mais as
                      colunas de hedge_ratio, spread, z_score, etc.
    """
    formation_window = config['formation_window']
    y_ticker = config['pair_to_backtest'][0]
    x_ticker = config['pair_to_backtest'][1]

    if len(df) < formation_window:
        print("Erro: O número de observações é menor que a janela de formação.")
        return None

    hedge_ratios = []
    spread_means = []
    spread_stds = []

    print("Iniciando cálculo do Z-Score dinâmico...")

    # Usamos tqdm padrão, que funciona bem em scripts de terminal
    for i in tqdm(range(formation_window, len(df)), desc="Calculando Parâmetros Walk-Forward"):
        window = df.iloc[i - formation_window : i]
        
        Y = window[y_ticker]
        X = sm.add_constant(window[x_ticker])
        model = sm.OLS(Y, X).fit()
        
        current_hedge_ratio = model.params.iloc[1]
        hedge_ratios.append(current_hedge_ratio)
        
        spread_window = window[y_ticker] - current_hedge_ratio * window[x_ticker]
        spread_means.append(spread_window.mean())
        spread_stds.append(spread_window.std())

    # Cria o DataFrame da estratégia a partir do ponto onde temos dados suficientes
    df_strategy = df.iloc[formation_window:].copy()
    df_strategy['hedge_ratio'] = hedge_ratios
    df_strategy['spread_mean'] = spread_means
    df_strategy['spread_std'] = spread_stds
    
    # Calcula o spread e o z-score para cada ponto no tempo
    df_strategy['spread'] = df_strategy[y_ticker] - df_strategy['hedge_ratio'] * df_strategy[x_ticker]
    df_strategy['z_score'] = (df_strategy['spread'] - df_strategy['spread_mean']) / df_strategy['spread_std']
    
    df_strategy.replace([np.inf, -np.inf], np.nan, inplace=True)
    df_strategy.dropna(inplace=True)
    
    # Se, após limpar, o DataFrame ficar vazio, retorne None
    if df_strategy.empty:
        logging.error("DataFrame vazio após limpeza de NaNs/Infs no Z-Score. Verifique os dados.")
        return None
        
    # (O fillna do z_score não é mais necessário, pois o dropna já o removeu)
    
    print("\nCálculo de Z-Score dinâmico concluído.")
    
    return df_strategy

def generate_hybrid_signals(df_strategy_input: pd.DataFrame, strategy_config: dict) -> pd.DataFrame:
    """
    Gera sinais de trading usando a estratégia híbrida (BBands + Filtros).
    Opera sobre a coluna 'spread' como se fosse o 'Close' de um ativo.
    Lê TODOS os parâmetros do 'strategy_config'.
    """
    logging.info("Iniciando geração de sinais com estratégia HÍBRIDA...")
    
    # 1. PREPARAÇÃO: A "PONTE"
    # Renomeia a coluna 'spread' para 'Close' temporariamente
    df = df_strategy_input.rename(columns={'spread': 'Close'})
    
    # 2. APLICAÇÃO DOS INDICADORES E FILTROS (Lendo do Config)
    
    # Base: Bandas de Bollinger (Sempre ativo)
    df = indicators.bollinger_bands(
        df, 
        window=strategy_config["bbands_window"], 
        num_std=strategy_config["bbands_std"]
    )

    # Interruptor 1: Filtro de Tendência
    if strategy_config["use_trend_filter"]:
        logging.info("Aplicando Filtro de Tendência (SMA)...")
        df = indicators.trend_sma(
            df, 
            window=strategy_config["trend_window"]
        )
    else:
        # Se o filtro está desligado, is_bullish/is_bearish serão True
        logging.info("Filtro de Tendência DESLIGADO.")
        
    # Interruptor 2: Filtro de Volatilidade (GARCH)
    garch_mode = strategy_config.get("garch_mode", "off")
    logging.info(f"Modo GARCH selecionado: {garch_mode}")

    if garch_mode == "gate":
        logging.info("GARCH em modo 'Gate' (Filtro 0/1).")
        df = models.volatility_filter(
            df,
            lookback=strategy_config["garch_lookback"],
            lower_q=strategy_config["garch_lower_q"],
            upper_q=strategy_config["garch_upper_q"]
        )
        df['vol_weight'] = 1.0 # Peso neutro
        
    elif garch_mode == "weight":
        logging.info("GARCH em modo 'Weight' (Ponderação).")
        df = models.calculate_volatility_weights(
            df,
            lookback=strategy_config["garch_lookback"],
            z_window=strategy_config["garch_weight_window"]
        )
        df['vol_signal'] = True # Portão sempre aberto
        
    else: # garch_mode == "off"
        logging.info("Modo GARCH DESLIGADO.")
        df['vol_signal'] = True # Portão sempre aberto
        df['vol_weight'] = 1.0 # Peso neutro

    df.dropna(inplace=True)
    if df.empty:
        logging.warning("DataFrame vazio após aplicação de indicadores. Nenhum sinal gerado.")
        return df_strategy_input.assign(position=0)

    # 3. LÓGICA DE SINAIS (DIREÇÃO)
    df["signal"] = 0
    position = 0
    exit_strategy = strategy_config["exit_strategy"]
    bb_middle = df["BB_middle"]
    
    logging.info(f"Gerando sinais com estratégia de saída: {exit_strategy}")

    for i in range(1, len(df)):
        price = df["Close"].iloc[i]
        bb_low = df["BB_lower"].iloc[i]
        bb_up = df["BB_upper"].iloc[i]
        
        # --- Condições de Filtro ---
        is_vol_ok = df["vol_signal"].iloc[i]

        if not strategy_config["use_trend_filter"]:
            is_bullish = True
            is_bearish = True
        else:
            is_bullish = price > df["trend"].iloc[i]
            is_bearish = price < df["trend"].iloc[i]

        # --- LÓGICA DE ENTRADA (DIREÇÃO) ---
        if position == 0 and is_bullish and is_vol_ok and price < bb_low:
            df.loc[df.index[i], "signal"] = 1
            position = 1
        elif position == 0 and is_bearish and is_vol_ok and price > bb_up:
            df.loc[df.index[i], "signal"] = -1
            position = -1

        # --- LÓGICA DE SAÍDA (DIREÇÃO) ---
        elif position == 1: # Se está comprado no spread
            if exit_strategy == 'flip' and price >= bb_up:
                df.loc[df.index[i], "signal"] = -1
                position = 0
            elif exit_strategy == 'zero_cross' and price >= bb_middle.iloc[i]:
                df.loc[df.index[i], "signal"] = -1
                position = 0
                
        elif position == -1: # Se está vendido no spread
            if exit_strategy == 'flip' and price <= bb_low:
                df.loc[df.index[i], "signal"] = 1
                position = 0
            elif exit_strategy == 'zero_cross' and price <= bb_middle.iloc[i]:
                df.loc[df.index[i], "signal"] = 1
                position = 0

    df["position"] = df["signal"].cumsum()
    logging.info("Geração de sinais HÍBRIDA concluída.")

    # 4. DEVOLVE as colunas de sinal e peso para o DataFrame original
    # (Remove 'Close' para evitar colisão com o 'Close' real do ativo)
    colunas_para_juntar = [
        'position', 'signal', 'vol_weight', 'vol_signal',
        'BB_upper', 'BB_middle', 'BB_lower', 'trend'
    ]
    # Filtra colunas que realmente existem no df
    colunas_finais = [col for col in colunas_para_juntar if col in df.columns]
    
    df_resultado = df_strategy_input.join(df[colunas_finais], how='left')

    df_resultado['position'] = df_resultado['position'].fillna(0)

    df_resultado['vol_signal'] = df_resultado['vol_signal'].infer_objects(copy=False).fillna(True)
    
    df_resultado['vol_weight'] = df_resultado['vol_weight'].fillna(1.0)
    
    return df_resultado # Retorna o DataFrame modificado