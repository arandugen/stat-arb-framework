import pandas as pd
import logging

def calculate_dynamic_hedge_benchmark(df_prices: pd.DataFrame, hedge_ratio_series: pd.Series, config: dict) -> pd.Series:
    """
    Benchmark 1: Hedge Dinâmico (Sempre Comprado no Spread)

    Simula uma estratégia que está sempre comprada no spread (long Ativo Y, short Ativo X),
    com a posição em X sendo rebalanceada a cada candle de acordo com o hedge ratio dinâmico.
    Isso isola o valor do timing (sinais de Z-Score) da sua estratégia principal.

    Args:
        df_prices (pd.DataFrame): DataFrame com os preços absolutos dos ativos do par.
        hedge_ratio_series (pd.Series): Série com o hedge ratio dinâmico calculado em strategy.py.
        config (dict): O dicionário de configuração do backtest.

    Returns:
        pd.Series: A curva de capital (equity curve) deste benchmark.
    """
    logging.info("Calculando benchmark: Hedge Dinâmico (Sempre Comprado)...")
    
    # Alinha os dataframes de preços e hedge ratio pelo índice
    df = pd.concat([df_prices, hedge_ratio_series.rename('hedge_ratio')], axis=1).dropna()
    
    y_ticker = config['pair_to_backtest'][0]
    x_ticker = config['pair_to_backtest'][1]
    initial_capital = config['initial_capital']

    # Dimensionamento da posição inicial (Dollar Neutral)
    # Assumimos que a posição é montada no primeiro candle e rebalanceada a partir daí
    price_Y = df[y_ticker].iloc[0]
    price_X = df[x_ticker].iloc[0]
    hedge_ratio = df['hedge_ratio'].iloc[0]
    
    qty_Y = initial_capital / (price_Y + (hedge_ratio * price_X))
    qty_X = -qty_Y * hedge_ratio

    # Calcula a variação de preço diária (P&L de cada candle)
    # P&L = (Qtd_Y * Variação_Preço_Y) + (Qtd_X * Variação_Preço_X)
    pnl_y = df[y_ticker].diff() * qty_Y
    pnl_x = df[x_ticker].diff() * qty_X

    # O P&L total de cada candle é a soma das duas pernas
    total_pnl = (pnl_y + pnl_x).fillna(0)
    
    # A curva de capital é o capital inicial mais o P&L acumulado
    equity_curve = initial_capital + total_pnl.cumsum()
    equity_curve.name = "dynamic_hedge_equity"
    
    return equity_curve


def calculate_buy_and_hold_benchmark(df_prices: pd.DataFrame, asset_ticker: str, config: dict) -> pd.Series:
    """
    Benchmark 2: Buy & Hold de um Ativo

    Simula a estratégia mais simples: comprar e segurar um dos ativos do par.

    Args:
        df_prices (pd.DataFrame): DataFrame com os preços absolutos, incluindo o do ativo.
        asset_ticker (str): O ticker do ativo a ser usado no benchmark.
        config (dict): O dicionário de configuração do backtest.

    Returns:
        pd.Series: A curva de capital (equity curve) deste benchmark.
    """
    logging.info(f"Calculando benchmark: Buy & Hold para {asset_ticker}...")
    initial_capital = config['initial_capital']
    
    # Pega a série de preços do ativo especificado
    asset_prices = df_prices[asset_ticker]
    
    # Calcula o retorno percentual acumulado desde o início
    returns = asset_prices.pct_change().fillna(0)
    cumulative_returns = (1 + returns).cumprod()
    
    # Aplica o retorno ao capital inicial
    equity_curve = initial_capital * cumulative_returns
    equity_curve.name = f"buy_hold_{asset_ticker}_equity"
    
    return equity_curve


def calculate_market_benchmark(df_market: pd.DataFrame, market_ticker: str, config: dict) -> pd.Series:
    """
    Benchmark 3: Mercado (ex: WIN$ ou IBOV)

    Simula o retorno de um índice de mercado.

    Args:
        df_market (pd.DataFrame): DataFrame contendo a coluna de fechamento do índice.
        market_ticker (str): Nome da coluna do ticker de mercado (ex: 'WIN$').
        config (dict): O dicionário de configuração do backtest.

    Returns:
        pd.Series: A curva de capital (equity curve) deste benchmark.
    """
    logging.info(f"Calculando benchmark: Mercado ({market_ticker})...")
    # Usa a mesma lógica do Buy & Hold
    return calculate_buy_and_hold_benchmark(df_market, market_ticker, config)


def calculate_risk_free_benchmark(dates_index: pd.DatetimeIndex, df_cdi: pd.DataFrame, config: dict) -> pd.Series:
    """
    Benchmark 4: Renda Fixa (CDI)

    Calcula o retorno acumulado da taxa CDI para o período do backtest.

    Args:
        dates_index (pd.DatetimeIndex): O índice de datas do DataFrame do backtest principal.
        df_cdi (pd.DataFrame): DataFrame carregado do CDI.parquet, com a coluna 'cdi_rate'.
        config (dict): O dicionário de configuração do backtest.

    Returns:
        pd.Series: A curva de capital (equity curve) deste benchmark.
    """
    logging.info("Calculando benchmark: Renda Fixa (CDI)...")
    initial_capital = config['initial_capital']
    
    # A taxa CDI é diária. Precisamos reindexar para as datas/horas do nosso backtest.
    # O ffill() garante que a taxa de um dia se aplique a todos os candles daquele dia.
    cdi_aligned = df_cdi.reindex(dates_index, method='ffill').fillna(0)
    
    # A taxa no arquivo já é decimal (ex: 0.0004). Para rentabilidade composta, somamos 1.
    # Como as taxas são diárias e nosso timeframe é intradiário, precisamos ajustar.
    # A forma mais robusta é calcular o fator diário e aplicá-lo uma vez por dia.
    cdi_daily_factor = (1 + cdi_aligned['cdi_rate']).resample('D').first().cumprod()
    
    # Realinha os fatores diários para o índice do backtest
    cumulative_returns = cdi_daily_factor.reindex(dates_index, method='ffill').fillna(1)
    
    equity_curve = initial_capital * cumulative_returns
    equity_curve.name = "cdi_equity"
    
    return equity_curve