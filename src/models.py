from arch import arch_model
import pandas as pd
import numpy as np
from arch.utility.exceptions import ConvergenceWarning, DataScaleWarning
import logging
import warnings

def volatility_filter(df: pd.DataFrame, lookback: int = 252,
                      lower_q: float = 0.025, upper_q: float = 0.975) -> pd.DataFrame:
    """
    Calcula a volatilidade prevista (GARCH) e gera um sinal binário (0/1).
    Usa RESCALA DINÂMICA para ser robusto a qualquer escala de dados.
    """
    # 1. Retornos originais (sem multiplicador)
    returns = df["Close"].diff().dropna()
    predicted_vol = pd.Series(np.nan, index=df.index)
    
    # 2. Alvo da reescala (um valor "saudável" para o GARCH)
    TARGET_SCALE = 100.0

    for i in range(lookback, len(returns)):
        train_window = returns.iloc[i - lookback : i]
        
        # --- LÓGICA DE RESCALA DINÂMICA ---
        scale = train_window.std()
        if pd.isna(scale) or scale < 1e-8:
            continue # Pula se a variância for zero ou NaN
            
        multiplier = TARGET_SCALE / scale
        rescaled_window = train_window * multiplier
        # --- FIM DA RESCALA ---
        
        try:
            model = arch_model(rescaled_window, vol="Garch", p=1, q=1, dist="t")
            
            # Suprime os avisos de DataScale que podem (raramente) ocorrer
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DataScaleWarning)
                warnings.simplefilter("ignore", ConvergenceWarning)
                res = model.fit(disp="off")
            
            forecast = res.forecast(horizon=1)
            
            # Pega a variância prevista (que está na escala rescaled)
            predicted_variance_rescaled = forecast.variance.values[-1, 0]
            
            # "Des-escala" a variância de volta à escala original
            # Var(k*X) = k^2 * Var(X)  =>  Var(X) = Var(k*X) / k^2
            predicted_variance_original = predicted_variance_rescaled / (multiplier ** 2)
            
            predicted_vol.iloc[i + 1] = np.sqrt(predicted_variance_original)
            
        except Exception:
            # Captura qualquer falha no GARCH e continua
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
    
    df["vol_signal"] = df["vol_signal"].fillna(False)
    
    return df

def calculate_volatility_weights(df: pd.DataFrame, 
                                 lookback: int = 100, 
                                 z_window: int = 126) -> pd.DataFrame:
    """
    Calcula um peso de alocação (0.5 a 1.5) baseado na vol GARCH prevista.
    Usa RESCALA DINÂMICA para ser robusto a qualquer escala de dados.
    """
    logging.info(f"Calculando pesos de GARCH (janela GARCH: {lookback}, janela Z: {z_window})...")
    
    # 1. Retornos originais (sem multiplicador)
    returns = df["Close"].diff().dropna()
    predicted_vol = pd.Series(np.nan, index=df.index)
    
    # 2. Alvo da reescala
    TARGET_SCALE = 100.0

    for i in range(lookback, len(returns)):
        train_window = returns.iloc[i - lookback : i]
        
        # --- LÓGICA DE RESCALA DINÂMICA ---
        scale = train_window.std()
        if pd.isna(scale) or scale < 1e-8:
            continue
            
        multiplier = TARGET_SCALE / scale
        rescaled_window = train_window * multiplier
        # --- FIM DA RESCALA ---
        
        try:
            model = arch_model(rescaled_window, vol="Garch", p=1, q=1, dist="t")
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DataScaleWarning)
                warnings.simplefilter("ignore", ConvergenceWarning)
                res = model.fit(disp="off")
                
            forecast = res.forecast(horizon=1)
            
            predicted_variance_rescaled = forecast.variance.values[-1, 0]
            predicted_variance_original = predicted_variance_rescaled / (multiplier ** 2)
            predicted_vol.iloc[i + 1] = np.sqrt(predicted_variance_original)
            
        except Exception:
            continue
            
    df["predicted_vol"] = predicted_vol.ffill()

    # 2. Calcula o Z-Score da volatilidade (sem lookahead)
    vol_mean = df["predicted_vol"].rolling(window=z_window).mean().shift(1)
    vol_std = df["predicted_vol"].rolling(window=z_window).std().shift(1)
    
    df["vol_zscore"] = (df["predicted_vol"] - vol_mean) / vol_std
    
    # 3. Converte Z-Score em Peso (1.0 - z_score)
    df["vol_weight"] = 1.0 - df["vol_zscore"]
    
    # 4. Limita (Corta) os pesos
    df["vol_weight"] = df["vol_weight"].clip(0.5, 1.5)
    
    # 5. Preenche NaNs (do início da janela rolante)
    df["vol_weight"] = df["vol_weight"].fillna(1.0)
    
    return df