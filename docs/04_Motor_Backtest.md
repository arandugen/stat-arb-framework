# 04. Metodologia do Motor de Backtest

## 1. Filosofia e Arquitetura

O coração do *pipeline* de simulação é o `src/backtesting.py`. Este módulo foi projetado para implementar uma **simulação iterativa (candle-a-candle)** que reflete condições de mercado realistas.

A arquitetura iterativa (`for i in range(1, len(df_backtest))`) garante que cada decisão de P&L, alocação e rebalanceamento seja tomada usando apenas os dados disponíveis até o *candle* `i-1` e `i`, eliminando o *lookahead bias*.

O motor recebe um único DataFrame (`df_with_signals`) que já contém os preços brutos dos ativos e as colunas de decisão (como `position`, `hedge_ratio` e `vol_weight`) calculadas pelo `src/strategy.py`.

## 2. Ciclo de Execução

A cada *candle* do *loop* de simulação, o motor executa uma sequência rigorosa de operações:

### Bloco A: Cálculo de P&L e Rendimento de Caixa
Este é o primeiro e mais crucial passo: determinar o P&L do *candle* atual antes de tomar qualquer nova decisão de alocação.

1.  **Se Posição Ativa (`current_pos != 0`):**
    * O P&L é calculado com base na variação de preço dos ativos (`curr_row[y_ticker] - prev_row[y_ticker]`) multiplicada pelas quantidades (`qty_Y`, `qty_X`) mantidas desde o *candle* anterior.
    * **Custo de Aluguel (BTC):** Se a posição for vendida (`qty_Y < 0` ou `qty_X < 0`), o custo de aluguel (calculado como `fee_per_candle`) é subtraído diretamente do P&L (`pnl -= custo_aluguel`).

2.  **Se Posição Neutra (`current_pos == 0`):**
    * Para resolver a limitação das "curvas de capital retas" (capital ocioso), o P&L é calculado como o rendimento do caixa.
    * O motor aplica a taxa de CDI (`cdi_rate_do_candle`, que foi pré-juntada ao DataFrame pelo `run_backtest.py`) ao valor total do portfólio do dia anterior (`prev_row['portfolio_value']`).

3.  **Atualização de Capital:** O `current_portfolio_value` é então atualizado com o `pnl` (seja ele do trade ou do CDI) antes que qualquer outra lógica seja executada.

### Bloco B: Decisão de Posição
O motor lê o "estado desejado" (coluna `position`) que foi pré-calculado pelo `src/strategy.py`. Ele simplesmente atualiza a variável de estado `current_pos` para corresponder à decisão da estratégia para aquele *candle*.

### Bloco C: Rebalanceamento e Dimensionamento de Posição
Este bloco calcula as quantidades de ativos (`qty_Y`, `qty_X`) a serem mantidas no *próximo* candle, com base no capital *recém-atualizado* (do Bloco A).

1.  **Juros Compostos:** O tamanho base do trade é recalculado a cada *candle* como uma porcentagem (`trade_size_pct`) do `current_portfolio_value`. Isso garante que os lucros e perdas sejam reinvestidos (compounding).

2.  **Ponderação de Volatilidade (GARCH):**
    * O motor lê o peso da volatilidade (`vol_weight`) calculado pelo GARCH em `src/models.py`.
    * O `final_trade_size` é ajustado por este peso (`trade_size_base * vol_weight`). Isso permite que o GARCH aumente ou diminua dinamicamente a alocação de capital no trade.
    * O código usa `curr_row.get('vol_weight', 1.0)` e `pd.isna(vol_weight)` para garantir que o *pipeline* não quebre com `KeyError` ou `NaN` durante as janelas de aquecimento do GARCH.

3.  **Cálculo de Quantidade (Hedge Dinâmico):**
    * As quantidades exatas (`qty_Y_abs`, `qty_X_abs`) são calculadas usando o `final_trade_size` e o `hedge_ratio` *dinâmico* (lido do `curr_row['hedge_ratio']`).
    * As quantidades finais (`qty_Y`, `qty_X`) são então ajustadas com os sinais (ex: `+qty_Y_abs`, `-qty_X_abs`) com base no `current_pos` (Comprado ou Vendido).

4.  **Posição Zerada:** Se `current_pos == 0`, as quantidades `qty_Y` e `qty_X` são explicitamente zeradas.

## 3. Parâmetros de Configuração (`BACKTEST_CONFIG`)

Este motor é controlado pelos seguintes parâmetros no `config.py`:

| Parâmetro (em `config.py`) | Função no `backtesting.py` |
| :--- | :--- |
| `initial_capital` | Define o valor inicial de `portfolio_value`. |
| `trade_size_pct` | Define a porcentagem do portfólio a ser usada em cada trade (Juros Compostos). |
| `short_rental_fee_annual` | A taxa anual de aluguel (BTC) para posições vendidas. |
| `candles_per_day` | Usado para converter a taxa de aluguel anual em `fee_per_candle`. |
| `trading_days_per_month`| Usado para converter a taxa de aluguel anual em `fee_per_candle`. |

*(**Nota:** O motor também depende implicitamente das colunas `cdi_rate`, `position`, `vol_weight` e `hedge_ratio` que são pré-processadas e unidas ao DataFrame pelo `run_backtest.py` e `src/strategy.py`).*