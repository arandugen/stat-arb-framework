import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.tsa.stattools as ts
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from statsmodels.tools.sm_exceptions import InterpolationWarning
from hurst import compute_Hc
import warnings
import logging

def calculate_half_life_ou(spread: pd.Series) -> float:
    """Calcula a meia-vida de reversão à média usando o modelo de Ornstein-Uhlenbeck."""
    spread = spread.dropna()
    delta_spread = spread.diff().dropna()
    spread_lagged = spread.shift(1).dropna()
    
    aligned_delta = delta_spread.loc[spread_lagged.index]
    if aligned_delta.empty or spread_lagged.empty:
        return np.nan

    model = sm.OLS(aligned_delta, sm.add_constant(spread_lagged)).fit()
    gamma = model.params.iloc[1]
    
    return np.log(2) / -gamma if gamma < 0 else np.inf

def validate_pair_engle_granger(df: pd.DataFrame,
                                freq_in_minutes: int,
                                validation_config: dict) -> dict:
    """
    Executa testes de cointegração (EG), estacionariedade (KPSS) e
    reversão à média (Hurst).
    KPSS e Hurst são calculados mesmo se o EG falhar.
    """
    if df.shape[1] != 2:
        return {'status': 'Erro: Não é um par', 'is_cointegrated': False}

    asset1, asset2 = df.columns[0], df.columns[1]

    # --- Lê os thresholds ---
    adf_limit = validation_config.get('ADF_P_VALUE_THRESHOLD', 0.05)
    coint_limit = validation_config.get('COINT_P_VALUE_THRESHOLD', 0.05)
    kpss_limit = validation_config.get('KPSS_P_VALUE_THRESHOLD', 0.05)
    hurst_limit = validation_config.get('HURST_THRESHOLD', 0.5)

    # --- Teste de Raiz Unitária (ADF) - Pré-filtro ---
    try:
        adf_p1 = ts.adfuller(df[asset1].dropna())[1]
        adf_p2 = ts.adfuller(df[asset2].dropna())[1]
        if adf_p1 < adf_limit or adf_p2 < adf_limit:
            return {'status': 'Falha ADF: Série individual estacionária', 'coint_p_value': np.nan,
                    'is_cointegrated': False, 'half_life_minutes': np.nan, 'kpss_p_value': np.nan,
                    'hurst_exponent': np.nan, 'is_stationary_robust': False}
    except Exception as e:
         logging.error(f"Erro no teste ADF para {asset1}/{asset2}: {e}")
         return {'status': f'Erro ADF: {e}', 'coint_p_value': np.nan,
                 'is_cointegrated': False, 'half_life_minutes': np.nan, 'kpss_p_value': np.nan,
                 'hurst_exponent': np.nan, 'is_stationary_robust': False}


    # --- Teste de Cointegração (EG) ---
    try:
        coint_p_value = ts.coint(df[asset1].dropna(), df[asset2].dropna())[1]
        is_cointegrated = coint_p_value < coint_limit
    except Exception as e:
        logging.error(f"Erro no teste de Cointegração EG para {asset1}/{asset2}: {e}")
        coint_p_value = np.nan
        is_cointegrated = False


    # --- Inicializa variáveis de resultado ---
    half_life_minutes = np.nan
    kpss_p_value = np.nan
    H = np.nan
    is_robust = False
    half_life_periods = np.nan
    spread = pd.Series(dtype=float) # Inicializa spread vazio

    # --- Calcula o Spread (SEMPRE) ---
    try:
        # Garante que não há NaNs antes do OLS
        df_clean = df.dropna()
        if len(df_clean) < 2: # OLS precisa de pelo menos 2 pontos
             raise ValueError("Dados insuficientes após dropna para calcular OLS.")

        ols_model = sm.OLS(df_clean[asset1], sm.add_constant(df_clean[asset2])).fit()
        hedge_ratio = ols_model.params.iloc[1]
        spread = (df[asset1] - hedge_ratio * df[asset2]).dropna() # Recalcula no df original para manter o índice
    except Exception as e:
        logging.error(f"Erro ao calcular Spread/OLS para {asset1}-{asset2}: {e}")
        # Se OLS falhar, não podemos calcular KPSS, Hurst ou Meia-Vida

    # --- Calcula KPSS e Hurst (SEMPRE, se o spread foi calculado) ---
    if not spread.empty:
        # Teste KPSS no spread
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=InterpolationWarning)
                _stat, kpss_p_value, _lags, _crit = ts.kpss(spread, regression='c', nlags='auto')
        except Exception as e:
            logging.warning(f"Falha ao calcular KPSS para {asset1}-{asset2}: {e}")
            kpss_p_value = np.nan

        # Teste Hurst no spread
        try:
            H_series_positive = spread - spread.min() + 1e-9 # Garante positividade
            H = compute_Hc(H_series_positive, kind='price', simplified=True)[0]
        except Exception as e:
            logging.warning(f"Falha ao calcular Hurst para {asset1}-{asset2}: {e}")
            H = np.nan

    # --- Calcula Meia-Vida (CONDICIONALMENTE) ---
    # Opção 1: Apenas se for cointegrado pelo EG
    if is_cointegrated and not spread.empty:
        half_life_periods = calculate_half_life_ou(spread)
        if np.isfinite(half_life_periods) and half_life_periods > 0:
            half_life_minutes = half_life_periods * freq_in_minutes

    # (Opcional) Opção 2: Se passar no KPSS (mesmo sem EG)
    kpss_passed = (not pd.isna(kpss_p_value)) and (kpss_p_value > kpss_limit)
    if kpss_passed and not spread.empty:
        half_life_periods = calculate_half_life_ou(spread)
    if np.isfinite(half_life_periods) and half_life_periods > 0:
        half_life_minutes = half_life_periods * freq_in_minutes


    # --- Define Robustez (Baseado em KPSS e Hurst) ---
    if (not pd.isna(kpss_p_value)) and (not pd.isna(H)):
        if (kpss_p_value > kpss_limit) and (H < hurst_limit):
            is_robust = True

    # --- Monta o dicionário final ---
    status = 'Sucesso'
    if pd.isna(coint_p_value) and pd.isna(kpss_p_value) and pd.isna(H):
        status = 'Falha Total nos Testes' # Se tudo falhou

    return {
        'status': status,
        'coint_p_value': coint_p_value,
        'is_cointegrated': is_cointegrated, # Resultado do EG
        'half_life_minutes': half_life_minutes, # Calculado condicionalmente
        'kpss_p_value': kpss_p_value, # Calculado sempre (se possível)
        'hurst_exponent': H, # Calculado sempre (se possível)
        'is_stationary_robust': is_robust # Baseado em KPSS e Hurst
    }

def validate_trio_johansen(df: pd.DataFrame) -> dict:
    """Executa o teste de Johansen para um trio."""
    if df.shape[1] != 3:
        return {'status': 'Erro: Não é um trio', 'coint_rank': -1}

    # det_order=-1 (sem termo determinístico), k_ar_diff=1 (1 lag)
    result = coint_johansen(df, det_order=-1, k_ar_diff=1)
    trace_stats = result.lr1
    crit_values_95 = result.cvt[:, 1]
    
    coint_rank = 0
    if trace_stats[0] > crit_values_95[0]:  # Testa r=0
        coint_rank = 1
    if trace_stats[1] > crit_values_95[1]:  # Testa r<=1
        coint_rank = 2

    return {
        'status': 'Sucesso',
        'coint_rank': coint_rank  # Retorna o número de relações de cointegração
    }