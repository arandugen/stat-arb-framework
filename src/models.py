from arch import arch_model
import pandas as pd
import numpy as np
from arch.utility.exceptions import ConvergenceWarning
import logging

def volatility_filter(df: pd.DataFrame, lookback: int = 252,
                      lower_q: float = 0.025, upper_q: float = 0.975) -> pd.DataFrame:

    """
    Calcula a volatilidade prevista (GARCH) e gera um sinal binário (0/1).
    """
    # CORREÇÃO: Usa 10000 para reescalar, como pedido pelo log
    returns = df["Close"].diff().dropna() * 1000
    predicted_vol = pd.Series(np.nan, index=df.index)

    for i in range(lookback, len(returns)):
        train_window = returns.iloc[i - lookback : i]
        
        if train_window.var() < 1e-8:
            continue
        
        try:
            model = arch_model(train_window, vol="Garch", p=1, q=1, dist="t")
            # CORREÇÃO: Removido 'solver' hardcoded
            res = model.fit(disp="off")
            
            forecast = res.forecast(horizon=1)
            predicted_vol.iloc[i + 1] = np.sqrt(forecast.variance.values[-1, 0])
            
        except (ConvergenceWarning, ValueError, Exception) as e:
            # Captura qualquer falha no GARCH
            continue

    df["predicted_vol"] = predicted_vol.ffill()

    # Cálculo do quantil expansivo (sem lookahead)
    df["vol_low"] = df["predicted_vol"].expanding(min_periods=lookback).quantile(lower_q)
    df["vol_up"] = df["predicted_vol"].expanding(min_periods=lookback).quantile(upper_q)

    # Cálculo do sinal (sem lookahead)
    df["vol_signal"] = (
        (df["predicted_vol"] > df["vol_low"].shift(1)) &
        (df["predicted_vol"] < df["vol_up"].shift(1))
    )
    
    # CORREÇÃO: Resolve FutureWarning com sintaxe moderna
    df["vol_signal"] = df["vol_signal"].fillna(False)
    
    return df

def calculate_volatility_weights(df: pd.DataFrame, 
                                 lookback: int = 100, 
                                 z_window: int = 126) -> pd.DataFrame:
    """
    Calcula um peso de alocação (0.5 a 1.5) baseado na 
    volatilidade GARCH prevista.
    """
    logging.info(f"Calculando pesos de GARCH (janela GARCH: {lookback}, janela Z: {z_window})...")
    
    # 1. Calcula a volatilidade prevista
    # CORREÇÃO: Usa 10000 para reescalar, como pedido pelo log
    returns = df["Close"].diff().dropna() * 1000
    predicted_vol = pd.Series(np.nan, index=df.index)

    for i in range(lookback, len(returns)):
        train_window = returns.iloc[i - lookback : i]
        if train_window.var() < 1e-8: continue
        try:
            model = arch_model(train_window, vol="Garch", p=1, q=1, dist="t")
            res = model.fit(disp="off")
            forecast = res.forecast(horizon=1)
            predicted_vol.iloc[i + 1] = np.sqrt(forecast.variance.values[-1, 0])
        except Exception:
            continue # Deixa np.nan
            
    # --- CORREÇÃO DO BUG (KeyError: 'vol_weight') ---
    
    # 1. REMOVE a linha com erro:
    # df['vol_weight'] = df['vol_weight'].fillna(1.0) 
    
    # 2. ADICIONA a linha que faltava:
    df["predicted_vol"] = predicted_vol.ffill()

    # --- Fim da Correção ---

    # 2. Calcula o Z-Score da volatilidade (sem lookahead)
    vol_mean = df["predicted_vol"].rolling(window=z_window).mean().shift(1)
    vol_std = df["predicted_vol"].rolling(window=z_window).std().shift(1)
    
    df["vol_zscore"] = (df["predicted_vol"] - vol_mean) / vol_std
    
    # 3. Converte Z-Score em Peso (1.0 - z_score)
    df["vol_weight"] = 1.0 - df["vol_zscore"]
    
    # 4. Limita (Corta) os pesos
    df["vol_weight"] = df["vol_weight"].clip(0.5, 1.5)
    
    # 5. Preenche NaNs (do início da janela rolante) com peso 1.0 (neutro)
    # CORREÇÃO: Resolve FutureWarning com sintaxe moderna
    df["vol_weight"] = df["vol_weight"].fillna(1.0)
    
    return df