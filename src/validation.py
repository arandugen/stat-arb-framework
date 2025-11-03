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

    # --- Inicializa variáveis de resultado ---
    half_life_minutes = np.nan
    kpss_p_value = np.nan
    H = np.nan
    is_robust = False
    half_life_periods = np.nan
    spread = pd.Series(dtype=float)
    coint_p_value = np.nan
    is_cointegrated = False
    
    # --- NOVAS VARIÁVEIS ---
    adf_p_value_Y = np.nan
    adf_p_value_X = np.nan
    status = 'Sucesso' # Começa como Sucesso

    # --- TESTE ADF INDIVIDUAL ---
    try:
        adf_p_value_Y = ts.adfuller(df[asset1].dropna())[1]
        adf_p_value_X = ts.adfuller(df[asset2].dropna())[1]
        
        
    except Exception as e:
         logging.error(f"Erro no teste ADF para {asset1}/{asset2}: {e}")
         status = 'Erro ADF'


    # --- Teste de Cointegração (EG) ---
    try:
        coint_p_value = ts.coint(df[asset1].dropna(), df[asset2].dropna())[1]
        is_cointegrated = coint_p_value < coint_limit
    except Exception as e:
        logging.error(f"Erro no teste de Cointegração EG para {asset1}/{asset2}: {e}")
        coint_p_value = np.nan
        is_cointegrated = False


    # --- Calcula o Spread (SEMPRE) ---
    try:
        df_clean = df.dropna()
        if len(df_clean) < 2: 
             raise ValueError("Dados insuficientes após dropna para calcular OLS.")

        ols_model = sm.OLS(df_clean[asset1], sm.add_constant(df_clean[asset2])).fit()
        hedge_ratio = ols_model.params.iloc[1]
        spread = (df[asset1] - hedge_ratio * df[asset2]).dropna()
    except Exception as e:
        logging.error(f"Erro ao calcular Spread/OLS para {asset1}-{asset2}: {e}")
        status = 'Erro OLS'

    # --- Calcula KPSS e Hurst ---
    if not spread.empty:
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=InterpolationWarning)
                _stat, kpss_p_value, _lags, _crit = ts.kpss(spread, regression='c', nlags='auto')
        except Exception as e:
            logging.warning(f"Falha ao calcular KPSS para {asset1}-{asset2}: {e}")
            kpss_p_value = np.nan

        try:
            H_series_positive = spread - spread.min() + 1e-9 
            H = compute_Hc(H_series_positive, kind='price', simplified=True)[0]
        except Exception as e:
            logging.warning(f"Falha ao calcular Hurst para {asset1}-{asset2}: {e}")
            H = np.nan
    elif status == 'Sucesso':
        status = 'Erro Spread Vazio'

    # --- Calcula Meia-Vida ---
    kpss_passed = (not pd.isna(kpss_p_value)) and (kpss_p_value > kpss_limit)
    
    # Calcula meia-vida se EG passou OU se KPSS passou
    if (is_cointegrated or kpss_passed) and not spread.empty:
        half_life_periods = calculate_half_life_ou(spread)
        if np.isfinite(half_life_periods) and half_life_periods > 0:
            half_life_minutes = half_life_periods * freq_in_minutes

    # --- Define Robustez (Baseado em KPSS e Hurst) ---
    if (not pd.isna(kpss_p_value)) and (not pd.isna(H)):
        if (kpss_p_value > kpss_limit) and (H < hurst_limit):
            is_robust = True

    # --- Monta o dicionário final ---
    if status == 'Sucesso' and pd.isna(coint_p_value) and pd.isna(kpss_p_value):
        status = 'Falha Testes Spread'

    return {
        'status': status,
        'adf_p_value_Y': adf_p_value_Y, 
        'adf_p_value_X': adf_p_value_X, 
        'coint_p_value': coint_p_value,
        'is_cointegrated': is_cointegrated,
        'kpss_p_value': kpss_p_value,
        'hurst_exponent': H,
        'is_stationary_robust': is_robust,
        'half_life_minutes': half_life_minutes
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

def filter_valid_pairs(df_validation_results: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra o DataFrame de resultados de validação para retornar
    apenas os pares que passaram nos critérios de trading.
    (Lógica movida de main_pipeline.py)
    """
    if df_validation_results.empty:
        return pd.DataFrame()
        
    # Critério Híbrido: Passa se (EG passou) OU (KPSS+Hurst passaram)
    valid_pairs = df_validation_results[
        (
            (df_validation_results['is_cointegrated'] == True) | 
            (df_validation_results['is_stationary_robust'] == True)
        )
    ].copy()
    
    return valid_pairs