# 05. Guia de Configuração (config.py)

##  Visão Geral

O arquivo `config.py` é o centro de controle nevrálgico de todo o *pipeline* de pesquisa. Ele permite ao pesquisador definir o escopo dos dados, os parâmetros dos testes estatísticos e a arquitetura exata da estratégia de trading, tudo sem alterar o código-fonte da aplicação.

Este documento detalha cada seção do `config.py` e seu impacto técnico nos módulos do sistema.

## Seção 1: Pipeline e Definição de Ativos

Esta seção controla o *pipeline* de ETL (Extração, Transformação, Carga) orquestrado pelo `run_etl.py`.

### `ASSET_PAIRS_TO_ANALYZE`
Define a lista de pares (tuplas) que serão baixados, processados e validados. O *framework* suporta uma arquitetura de fontes mistas, onde cada ativo é definido por `(TICKER, FONTE)`.

* **`TICKER`**: O nome do ativo (ex: `'SUZB3'`, `'BRL=X'`).
* **`FONTE`**: A origem dos dados (`'mt5'` ou `'yfinance'`).

O `run_etl.py` lê esta lista, agrupa os tickers únicos por fonte e chama a função de coleta apropriada em `src/data_collection.py`. O `src/processing.py` então usa os nomes dos tickers para encontrar os arquivos `.parquet` brutos e criar os arquivos de *spread* logarítmico (ex: `BRL=X_DOL$_log_prices.parquet`).

```python
# Exemplo de configuração de pares
ASSET_PAIRS_TO_ANALYZE = [
    # Par Misto (YFinance + MT5)
    (('BRL=X', 'yfinance'), ('DOL$', 'mt5')),
    
    # Par Puro (MT5 + MT5)
    (('SUZB3', 'mt5'), ('KLBN11', 'mt5'))
]
```

### `BENCHMARK_TICKERS`

Define os ativos de *benchmark* (ex: Índice, CDI) que também devem ser baixados pelo `run_etl.py`.

## Seção 2: Período e Timeframe

Parâmetros globais que controlam a coleta de dados em `src/data_collection.py` e os cálculos de janela em `src/utils.py`.

  * `data_inicio`, `data_fim`: Define o período de extração dos dados.
  * `timeframe`: (String, ex: `"D1"`, `"H1"`) Define a granularidade dos dados. Este valor é crucial, pois é usado pela função `utils.calculate_time_parameters` para derivar automaticamente os parâmetros `candles_per_day` e `freq_in_minutes`, que são então injetados no `BACKTEST_CONFIG`.

## Seção 3: `VALIDATION_CONFIG`

Este dicionário fornece os limiares (thresholds) para os testes estatísticos em `src/validation.py`.

| Parâmetro | Módulo Afetado | Descrição Técnica |
| :--- | :--- | :--- |
| `ADF_P_VALUE_THRESHOLD` | `validation.validate_pair_engle_granger` | **p-valor \< X**. Limiar para o teste ADF nas séries individuais. Se qualquer ativo for estacionário (p-valor \< X), o par é descartado. |
| `COINT_P_VALUE_THRESHOLD` | `validation.validate_pair_engle_granger` | **p-valor \< X**. Limiar para o teste Engle-Granger nos resíduos (spread). Define a variável `is_cointegrated`. |
| `KPSS_P_VALUE_THRESHOLD`| `validation.validate_pair_engle_granger` | **p-valor \> X**. Limiar para o teste KPSS no spread. A H₀ é de estacionariedade, portanto, p-valores *altos* são desejados. |
| `HURST_THRESHOLD` | `validation.validate_pair_engle_granger` | **Hurst \< X**. Limiar para o Expoente de Hurst. Valores \< 0.5 indicam reversão à média. |

*Nota: Os resultados de `KPSS` e `HURST` são combinados para definir o booleano `is_stationary_robust`, permitindo uma filtragem mais rigorosa do que o simples `is_cointegrated` do EG.*

## Seção 4: `STRATEGY_CONFIG`

Este é o painel de controle principal para a análise de sensibilidade da estratégia híbrida (`generate_hybrid_signals` em `src/strategy.py`).

| Parâmetro | Módulo(s) Afetado(s) | Descrição Técnica |
| :--- | :--- | :--- |
| `bbands_window` | `indicators.bollinger_bands` | (Int) Janela de lookback (N) para a SMA e o StDev das Bandas de Bollinger. |
| `bbands_std` | `indicators.bollinger_bands` | (Float) Multiplicador (K) do desvio padrão (StdDev) para os limiares de entrada (`BB_upper`/`BB_lower`). |
| `use_trend_filter`| `strategy.generate_hybrid_signals` | (Bool) Interruptor mestre do filtro de tendência. Se `False`, o `trend_window` é ignorado e os sinais de entrada são permitidos em qualquer regime. |
| `trend_window` | `indicators.trend_sma` | (Int) Janela (N) da SMA longa usada como filtro de regime (usado apenas se `use_trend_filter=True`). |
| `garch_mode` | `strategy.generate_hybrid_signals` | (String) Define o modo de operação do GARCH: `'off'`, `'gate'`, ou `'weight'`. |
| `garch_lookback`| `models.volatility_filter`, `models.calculate_volatility_weights` | (Int) Janela rolante (N) para treinar o GARCH(1,1) a cada candle. *(Aviso: O `config.py` lista este parâmetro duas vezes. O Python usará a última definição: `100`)*. |
| `garch_weight_window`| `models.calculate_volatility_weights` | (Int) Janela (N) para o Z-Score da volatilidade (usado apenas no modo `'weight'`). |
| `garch_lower_q` | `models.volatility_filter` | (Float) Quantil inferior de vol. para filtrar trades (usado apenas no modo `'gate'`). |
| `garch_upper_q` | `models.volatility_filter` | (Float) Quantil superior de vol. para filtrar trades (usado apenas no modo `'gate'`). |
| `exit_strategy` | `strategy.generate_hybrid_signals` | (String) Define a lógica de saída: `'zero_cross'` (saída na `BB_middle`) ou `'flip'` (saída na banda oposta). |

## Seção 5: `BACKTEST_CONFIG`

Este dicionário controla o ambiente do motor de simulação `backtesting.run_backtest`.

| Parâmetro | Módulo(s) Afetado(s) | Descrição Técnica |
| :--- | :--- | :--- |
| `formation_months` | `utils.calculate_formation_window`, `strategy.calculate_dynamic_zscore` | (Int) Define a janela de lookback (em meses) para o cálculo do Z-Score e Hedge Ratio dinâmicos. |
| `trading_days_per_month`| `utils.calculate_formation_window`, `backtesting.run_backtest` | (Int) Estimativa de dias úteis, usada para converter meses em candles e para anualizar o custo de aluguel. |
| `trading_hours_per_day`| `utils.calculate_time_parameters` | (Int) Define o "pregão" (ex: 8 para B3, 24 para FX). Usado para derivar `candles_per_day`. |
| `initial_capital` | `backtesting.run_backtest` | (Float) O valor inicial (BRL) do portfólio. |
| `trade_size_pct` | `backtesting.run_backtest` | (Float) Percentual do `current_portfolio_value` a ser alocado em cada trade. Definir como `1.0` ativa os juros compostos. |
| `short_rental_fee_annual`| `backtesting.run_backtest` | (Float) Taxa anual (ex: `0.02` para 2%) do custo de aluguel (BTC) para posições vendidas. O `backtesting.py` a converte em `fee_per_candle`. |

