import pandas as pd
import logging

def run_backtest(df_with_signals: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Executa o backtest iterativo com LÓGICA REALISTA AVANÇADA.
    (Juros Compostos, Custo de Aluguel, Ponderação GARCH E RENDIMENTO DE CAIXA PARCIAL)
    """
    logging.info("--- Iniciando Backtest com Lógica Realista (Juros Compostos, Custo, Ponderação GARCH e Rendimento de Caixa Parcial) ---")

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
        
        # ======================================================================
        # --- A. CÁLCULO DE P&L E ATUALIZAÇÃO DO PORTFÓLIO (LÓGICA CORRIGIDA) ---
        # ======================================================================
        
        # 1. Calcular o P&L do Trade (se houver)
        #    (qty_Y e qty_X são da *iteração anterior*, o que está correto)
        pnl_trade = 0.0
        capital_alocado_prev = 0.0 # Capital que estava no trade
        
        if current_pos != 0:
            pnl_trade = (qty_Y * (curr_row[y_ticker] - prev_row[y_ticker])) + \
                        (qty_X * (curr_row[x_ticker] - prev_row[x_ticker]))
            
            # Subtrai o custo de aluguel do P&L do trade
            if fee_per_candle > 0:
                valor_posicao_vendida = 0
                if qty_Y < 0: valor_posicao_vendida = abs(qty_Y * prev_row[y_ticker])
                elif qty_X < 0: valor_posicao_vendida = abs(qty_X * prev_row[x_ticker])
                custo_aluguel = valor_posicao_vendida * fee_per_candle
                pnl_trade -= custo_aluguel
            
            # Calcula o capital que estava alocado no trade
            capital_alocado_prev = abs(qty_Y * prev_row[y_ticker]) + abs(qty_X * prev_row[x_ticker])

        # 2. Calcular o P&L do Caixa (Capital não alocado)
        capital_em_caixa_prev = prev_row['portfolio_value'] - capital_alocado_prev
        
        # Garante que o caixa não seja negativo (em caso de alavancagem > 1)
        if capital_em_caixa_prev < 0:
            capital_em_caixa_prev = 0 
            # (Nota: Em um sistema real, caixa negativo pagaria juros (custo),
            # mas para o CDI, assumimos 0)

        # O 'df_ready_for_backtest' (passado para esta função)
        # DEVE conter a coluna 'cdi_rate' (preparada em 'run_backtest.py')
        cdi_rate_do_candle = curr_row.get('cdi_rate', 0.0)
        pnl_caixa = capital_em_caixa_prev * cdi_rate_do_candle
        
        # 3. P&L Total e Atualização do Portfólio
        pnl_total = pnl_trade + pnl_caixa
        
        current_portfolio_value = prev_row['portfolio_value'] + pnl_total
        df_backtest.iloc[i, df_backtest.columns.get_loc('portfolio_value')] = current_portfolio_value
        df_backtest.iloc[i, df_backtest.columns.get_loc('pnl')] = pnl_total

        # ======================================================================
        # --- B. LÓGICA DE DECISÃO: LER O SINAL DA ESTRATÉGIA ---
        # ======================================================================
        desired_pos = curr_row.get('position', 0)
        
        if desired_pos != current_pos:
            current_pos = desired_pos
        
        # ======================================================================
        # --- C. REBALANCEAMENTO / JUROS COMPOSTOS / PONDERAÇÃO GARCH ---
        # ======================================================================
        #    (Calcula as quantidades Qty_Y e Qty_X para o *próximo* candle)
        
        if current_pos != 0:
            # Usa o capital recém-atualizado (juros compostos)
            trade_size_base = current_portfolio_value * config.get('trade_size_pct', 1.0)
            
            vol_weight = curr_row.get('vol_weight', 1.0)
            if pd.isna(vol_weight):
                vol_weight = 1.0
            
            # Aplica a Ponderação (seja 1.0, 0.8, ou 0.7 do GARCH)
            final_trade_size = trade_size_base * vol_weight
            
            price_Y = curr_row[y_ticker]
            price_X = curr_row[x_ticker]
            hedge_ratio = curr_row['hedge_ratio']

            denominator = price_Y + (hedge_ratio * price_X)
            if denominator <= 0 or pd.isna(denominator):
                qty_Y, qty_X = 0, 0 # Segurança
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