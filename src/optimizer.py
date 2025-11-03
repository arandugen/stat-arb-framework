from typing import Dict, Any, Tuple
import pandas as pd
from scipy.optimize import differential_evolution

# Importando as funções de indicadores, estratégia e backtester
from src.indicators import sma, bollinger_bands, trend_sma
from src.strategy import trading_strategy
from src.backtesting import simulate_portfolio


def objective_function(params: list, df: pd.DataFrame, initial_capital: float) -> float:
    """
    Função objetivo que executa a simulação completa e retorna
    o VALOR FINAL DA CARTEIRA negativo para minimização.
    """
    # 1. Desempacota o novo parâmetro trend_w
    trend_w, sma_w, bb_w, bb_std = params
    trend_w, sma_w, bb_w = int(trend_w), int(sma_w), int(bb_w)

    df_temp = df.copy()

    # 2. Adicionar Indicadores e Sinais usando os parâmetros da otimização
    # ATUALIZADO: Usa trend_w em vez de um valor fixo
    df_temp = trend_sma(df_temp, window=trend_w)
    df_temp = sma(df_temp, window=sma_w, output_col="SMA_optimized")
    df_temp = bollinger_bands(df_temp, window=bb_w, num_std=bb_std)

    df_temp.dropna(inplace=True)
    
    if df_temp.empty:
        return 0 
    
    df_with_signals = trading_strategy(
        df_temp,
        sma_col="SMA_optimized",
        bb_lower_col="BB_lower",
        bb_upper_col="BB_upper",
        trend_col="trend"
    )

    # 3. Simular a Carteira com base nos sinais
    df_portfolio = simulate_portfolio(df_with_signals, initial_capital)

    # 4. A métrica a ser otimizada é o valor final da carteira
    final_portfolio_value = df_portfolio['portfolio_value'].iloc[-1]
    
    # Retorna o negativo para que o otimizador maximize o valor
    return -final_portfolio_value

def find_best_params(df: pd.DataFrame, initial_capital: float = 100000.0) -> Tuple[Dict[str, Any], float]:
    """
    Usa Evolução Diferencial para encontrar os melhores parâmetros
    que maximizam o valor final da carteira.
    """
    bounds = [
        (20, 120),   # Limites para trend_window
        (10, 200),   # Limites para sma_window (se ainda for usar)
        (10, 50),    # Limites para bb_window
        (1.0, 2.5)   # Limites para bb_std
    ]

    result = differential_evolution(
        func=objective_function,    
        bounds=bounds,
        args=(df, initial_capital),                 
        integrality=[True, True, True, False],
        strategy='best1bin',
        maxiter=15,
        popsize=10,
        tol=0.01,
        mutation=(0.5, 1),
        recombination=0.7,
        disp=False,
        workers=-1,
        updating='deferred',
        seed=42
    )

    best_final_value = -result.fun
    best_return = (best_final_value / initial_capital) - 1

    best_params_list = result.x
    
    best_params_dict = {
        'trend_window': int(best_params_list[0]),
        'sma_window': int(best_params_list[1]),
        'bb_window': int(best_params_list[2]),
        'bb_std': float(round(best_params_list[3], 4)) 
    }

    return best_params_dict, best_return