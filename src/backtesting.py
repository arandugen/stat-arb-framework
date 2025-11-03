import pandas as pd
import logging

def run_backtest(df_with_signals: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Executa o backtest iterativo da estratégia com LÓGICA REALISTA.
    (Juros Compostos, Custo de Aluguel, Ponderação GARCH E RENDIMENTO DE CAIXA)
    """
    logging.info("--- Iniciando Backtest com Lógica Realista (Juros Compostos, Custo, Ponderação GARCH e Rendimento de Caixa) ---")

    # --- 1. PREPARAÇÃO ---
    df_backtest = df_with_signals.copy()
    initial_capital = config['initial_capital']
    df_backtest['actual_position'] = 0.0
    df_backtest['portfolio_value'] = initial_capital
    df_backtest['pnl'] = 0.0

    # --- 2. VARIÁVEIS DE ESTADO DO LOOP ---
    current_pos = 0
    qty_Y, qty_X = 0, 0
    
    # Validação dos tickers
    if 'pair_to_backtest' not in config or len(config['pair_to_backtest']) < 2:
        logging.error("Erro fatal: 'pair_to_backtest' não encontrado ou incompleto no config.")
        return pd.DataFrame()
        
    y_ticker = config['pair_to_backtest'][0]
    x_ticker = config['pair_to_backtest'][1]

    # Parâmetros para o custo de aluguel
    short_rental_fee_annual = config.get('short_rental_fee_annual', 0.0)
    fee_per_candle = 0.0
    if short_rental_fee_annual > 0:
        candles_per_day = config.get('candles_per_day', 1) 
        trading_days_per_month = config.get('trading_days_per_month', 21)
        candles_per_year = candles_per_day * trading_days_per_month * 12
        
        if candles_per_year > 0:
            fee_per_candle = short_rental_fee_annual / candles_per_year
            logging.info(f"Custo de aluguel por candle calculado: {fee_per_candle:.8f}")
        else:
            logging.warning("candles_per_year é 0. Custo de aluguel não será aplicado.")

    # --- 3. LOOP DE BACKTEST ---
    for i in range(1, len(df_backtest)):
        prev_row = df_backtest.iloc[i - 1]
        curr_row = df_backtest.iloc[i]
        
        # --- A. CÁLCULO DE P&L E ATUALIZAÇÃO DO PORTFÓLIO (MODIFICADO) ---
        
        if current_pos != 0:
            # P&L da Posição (Trade)
            pnl = (qty_Y * (curr_row[y_ticker] - prev_row[y_ticker])) + \
                  (qty_X * (curr_row[x_ticker] - prev_row[x_ticker]))
            
            # Custo de Aluguel (se vendido)
            if fee_per_candle > 0:
                valor_posicao_vendida = 0
                if qty_Y < 0: valor_posicao_vendida = abs(qty_Y * prev_row[y_ticker])
                elif qty_X < 0: valor_posicao_vendida = abs(qty_X * prev_row[x_ticker])
                custo_aluguel = valor_posicao_vendida * fee_per_candle
                pnl -= custo_aluguel
        else:
            # --- NOVO: P&L do Caixa (Rendimento CDI) ---
            # Se não há posição, o P&L é o rendimento do caixa
            cdi_rate_do_candle = curr_row.get('cdi_rate', 0.0)
            pnl = prev_row['portfolio_value'] * cdi_rate_do_candle

        # Atualização do Portfólio (Funciona para ambos os casos)
        current_portfolio_value = prev_row['portfolio_value'] + pnl
        df_backtest.iloc[i, df_backtest.columns.get_loc('portfolio_value')] = current_portfolio_value
        df_backtest.iloc[i, df_backtest.columns.get_loc('pnl')] = pnl

        # B. LÓGICA DE DECISÃO: LER O SINAL DA ESTRATÉGIA
        desired_pos = curr_row.get('position', 0)
        
        if desired_pos != current_pos:
            current_pos = desired_pos
        
        # C. REBALANCEAMENTO / JUROS COMPOSTOS / PONDERAÇÃO GARCH
        
        if current_pos != 0:
            trade_size_base = current_portfolio_value * config.get('trade_size_pct', 1.0)
            
            vol_weight = curr_row.get('vol_weight', 1.0)
            if pd.isna(vol_weight):
                vol_weight = 1.0
            
            final_trade_size = trade_size_base * vol_weight
            
            price_Y = curr_row[y_ticker]
            price_X = curr_row[x_ticker]
            hedge_ratio = curr_row['hedge_ratio']

            denominator = price_Y + (hedge_ratio * price_X)
            if denominator <= 0 or pd.isna(denominator):
                qty_Y, qty_X = 0, 0
            else:
                qty_Y_abs = final_trade_size / denominator
                qty_X_abs = qty_Y_abs * hedge_ratio

                if current_pos == 1:
                    qty_Y, qty_X = qty_Y_abs, -qty_X_abs
                elif current_pos == -1:
                    qty_Y, qty_X = -qty_Y_abs, qty_X_abs
        else:
            qty_Y, qty_X = 0, 0 # Zera as quantidades se a posição for neutra

        df_backtest.iloc[i, df_backtest.columns.get_loc('actual_position')] = current_pos

    logging.info("--- Backtest iterativo concluído. ---")
    
    return df_backtest