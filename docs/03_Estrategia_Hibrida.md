# 03. Metodologia da Estratégia Híbrida

## 1. Visão Geral

A lógica de geração de sinais, implementada em `src/strategy.py`, é um motor híbrido e modular projetado para executar estratégias de reversão à média em ativos sintéticos.

O sistema trata o **spread** (o resíduo da regressão OLS entre dois ativos cointegrados) como o ativo-alvo primário. A geração de sinais é desacoplada em um módulo-base obrigatório (Bandas de Bollinger) e uma série de filtros de regime opcionais (Tendência e Volatilidade).

Essa arquitetura permite que o pesquisador, através de um único arquivo de configuração (`config.py`), ative, desative e parametrize dinamicamente cada componente do modelo para realizar análises de sensibilidade robustas e otimizações.

## 2. Componentes da Estratégia

A geração de sinal (`generate_hybrid_signals`) é um processo sequencial que aplica os seguintes módulos:

### 2.1. Ativo-Alvo: O Spread

A estratégia não opera sobre o preço bruto, mas sobre o *spread* calculado pela função `calculate_dynamic_zscore`. Para compatibilidade com os módulos de indicadores (originalmente do [primeiro repositório de estudo](https://github.com/arandugen/mreversion-bbands-strategy)), o *spread* é renomeado internamente para "Close" (`df = df_strategy_input.rename(columns={'spread': 'Close'})`). Todos os indicadores subsequentes são calculados sobre esta série.

### 2.2. Módulo Base: Sinais de Entrada (Bollinger Bands)

A decisão de entrada é governada por uma estratégia padrão de Bandas de Bollinger (BBands), implementada em `src/indicators.py`.
* **Sinal de Compra (Long):** `spread < BB_lower`.
* **Sinal de Venda (Short):** `spread > BB_upper`.
* **Parâmetros:** `bbands_window` (janela da média e std) e `bbands_std` (limiar de desvio).

### 2.3. Módulo Opcional 1: Filtro de Regime de Tendência (SMA)

Este filtro subordina os sinais de reversão à média (Bollinger) à tendência de longo prazo do *spread*.
* **Controle:** `use_trend_filter: True/False`.
* **Mecânica (Se `True`):**
    1.  Uma SMA longa (janela `trend_window`) é calculada sobre o *spread*.
    2.  O sistema define um regime "Bullish" (`spread > SMA`) ou "Bearish" (`spread < SMA`).
    3.  A entrada é **bloqueada** se o sinal for contra o regime (ex: um sinal de Compra (`price < BB_lower`) só é permitido se o regime já for "Bullish").
* **Mecânica (Se `False`):**
    1.  Os portões de regime (`is_bullish`, `is_bearish`) são permanentemente definidos como `True`.
    2.  Isso permite que a estratégia opere como um modelo puro de reversão à média, que foi empiricamente mais lucrativo em testes preliminares.

### 2.4. Módulo Opcional 2: Filtro/Ponderador de Volatilidade (GARCH)

Este módulo (`src/models.py`) avalia a volatilidade dos *retornos do spread* (calculados via `.diff()`) usando um modelo GARCH(1,1).
* **Controle:** `garch_mode: 'off' | 'gate' | 'weight'`.
* **Mecânica dos Modos:**
    * `'off'`: Nenhum cálculo de GARCH é executado. O peso da posição é neutro (1.0).
    * `'gate'`: Utiliza a função `models.volatility_filter`. A estratégia só pode operar (`vol_signal = True`) quando a volatilidade prevista está dentro de quantis "ideais" (ex: não está nem muito baixa, nem estourando). O tamanho da posição é binário (1 ou 0).
    * `'weight'`: Utiliza a função `models.calculate_volatility_weights`. A estratégia pode operar *sempre* (`vol_signal = True`), mas o **tamanho da posição** é dinamicamente ponderado (ex: 0.5x a 1.5x). A ponderação é baseada em um Z-Score da volatilidade prevista, implementando uma tese de "inversão de volatilidade" (alocar menos em vol alta, mais em vol baixa).

### 2.5. Módulo Opcional 3: Estratégia de Saída

Controla a lógica de realização de lucro (saída) após uma entrada ser acionada.
* **Controle:** `exit_strategy: 'zero_cross' | 'flip'`.
* **Mecânica dos Modos:**
    * `'zero_cross'`: Encerra a posição assim que o *spread* reverte para sua média (`BB_middle`). Captura o lucro da reversão pura.
    * `'flip'`: Encerra a posição apenas quando o *spread* reverte totalmente até a banda oposta. Tenta capturar o movimento completo do canal.

## 3. Painel de Controle para Análise de Sensibilidade (`config.py`)

A modularidade do `src/strategy.py` permite uma poderosa análise de sensibilidade. Todas as hipóteses podem ser testadas dinamicamente alterando apenas o `STRATEGY_CONFIG`, sem reescrever o código.

| Parâmetro de Configuração | Módulo Afetado | Descrição Técnica da Função |
| :--- | :--- | :--- |
| `bbands_window` | `indicators.bollinger_bands` | Define a janela de lookback (N) para a SMA e o StDev das bandas. |
| `bbands_std` | `indicators.bollinger_bands` | Define o multiplicador (K) do desvio padrão (StdDev) para os limiares de entrada. |
| `use_trend_filter` | `strategy.generate_hybrid_signals` | (Bool) Ativa/desativa o filtro de regime de tendência (SMA longa). |
| `trend_window` | `indicators.trend_sma` | Define a janela de lookback (N) da SMA de tendência (usada apenas se `use_trend_filter=True`). |
| `garch_mode` | `strategy.generate_hybrid_signals` | (String) Seleciona o modo de operação do GARCH: `'off'`, `'gate'` (filtro 0/1) ou `'weight'` (ponderação). |
| `garch_lookback` | `models.volatility_filter`, `models.calculate_volatility_weights` | Define a janela rolante (N) para treinar o GARCH(1,1) a cada candle. |
| `garch_weight_window`| `models.calculate_volatility_weights` | Define a janela (N) para o Z-Score da volatilidade (usado apenas no modo `'weight'`). |
| `garch_lower_q` | `models.volatility_filter` | Quantil inferior de vol. para filtrar trades (usado apenas no modo `'gate'`). |
| `garch_upper_q` | `models.volatility_filter` | Quantil superior de vol. para filtrar trades (usado apenas no modo `'gate'`). |
| `exit_strategy` | `strategy.generate_hybrid_signals` | (String) Define a lógica de saída: `'zero_cross'` (saída na média) ou `'flip'` (saída na banda oposta). |

## 4. Aplicação em Pesquisa

Esta arquitetura permite ao pesquisador responder perguntas complexas de forma eficiente:
* A estratégia de reversão pura (`use_trend_filter: False`) supera a filtrada?
* É mais lucrativo sair na média (`zero_cross`) ou no extremo (`flip`)?
* O GARCH adiciona valor como um filtro (`gate`) ou como um ponderador (`weight`)?
* Qual é a combinação ótima de `bbands_window` e `bbands_std` para maximizar o Sharpe Ratio? (Esta pergunta será futuramente respondida pelo `optimizer.py`).