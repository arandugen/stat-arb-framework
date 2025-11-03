# 07. Otimização de Parâmetros (Roadmap)

## 1. Status: Não Implementado

Esta seção descreve uma funcionalidade crítica que é o próximo passo lógico na evolução deste *framework*: a **otimização de parâmetros**.

Atualmente, o *pipeline* principal (`main_pipeline.py`) executa backtests usando um **conjunto único e estático** de parâmetros definidos no `config.py` (ex: `STRATEGY_CONFIG`). A análise de sensibilidade é um processo manual que exige que o pesquisador altere este arquivo e re-execute o *pipeline*.

O arquivo `optimizer.py` existente é um artefato do [primeiro repositório de estudo](https://github.com/arandugen/mreversion-bbands-strategy), e **não está integrado** ao *pipeline* atual.

## 2. O Desafio da Refatoração: Integrando o Otimizador

A implementação desta funcionalidade exigirá uma refatoração significativa para integrar o `optimizer.py` ao motor de simulação realista (`backtesting.py`).

1.  **Substituição da Função Objetivo:** A `objective_function` atual chama o backtester vetorizado e simplista `simulate_portfolio`. Esta função deve ser reescrita para chamar o orquestrador `run_backtest.py` ou, mais eficientemente, chamar diretamente as funções `strategy.generate_hybrid_signals` e `backtesting.run_backtest`.
2.  **Custo Computacional:** O motor `backtesting.run_backtest` é iterativo (candle-a-candle) e muito mais "caro" (lento) do que o `simulate_portfolio`. Isso torna a escolha do algoritmo de otimização ainda mais crucial.

## 3. Métrica-Alvo: Índice de Sharpe

O otimizador atual (`optimizer.py`) está configurado para maximizar o `final_portfolio_value` (Retorno Total).

O novo *pipeline* de otimização será focado em maximizar o **Retorno Ajustado ao Risco**. A `objective_function` será modificada para calcular o **Índice de Sharpe** da curva de capital resultante, utilizando a função `utils.sharpe_ratio`.

Como os otimizadores são, por padrão, minimizadores, a função retornará `-sharpe_ratio`.

## 4. Modos de Otimização Planejados

O *framework* suportará dois modos de otimização, cada um com diferentes características filosóficas e casos de uso:

### 4.1. Modo 1: Evolução Diferencial (Stochastic / Global Search)

* **Algoritmo:** `scipy.optimize.differential_evolution`.
* **Como Funciona:** Este é um otimizador *estocástico* (baseado em aleatoriedade) e *global*. Ele funciona criando uma "população" de conjuntos de parâmetros (ex: 50 combinações). A cada "geração" (iteração), ele "cruza" e "muta" (combina) os melhores parâmetros da geração anterior para criar uma nova população, "evoluindo" em direção a uma solução ótima.
* **O que Testa:** É ideal para **exploração**. Ele é excelente para "mapear" um espaço de parâmetros grande e complexo, sendo muito eficaz em evitar "mínimos locais" (soluções que parecem boas, mas não são as melhores). Por exemplo, ele pode testar uma `bbands_window` de `20` e `100` na mesma geração, descobrindo "bolsões" de lucratividade que uma busca local ignoraria.
* **Desvantagem:** Requer um grande número de iterações (chamadas à `objective_function`) para convergir, sendo computacionalmente caro.

### 4.2. Modo 2: Otimização Bayesiana (Sequential / Smart Search)

* **Algoritmo:** (Ex: `scikit-optimize` ou `hyperopt`).
* **Como Funciona:** Este é um otimizador *sequencial* e *inteligente*. Ele trata a `objective_function` como uma "caixa-preta". A cada iteração, ele usa os resultados anteriores (ex: "Janela 20, Std 2.0 -> Sharpe 0.5") para construir um modelo estatístico (um Processo Gaussiano) que "aprende" o mapa de parâmetros. Ele então escolhe o *próximo* conjunto de parâmetros para testar com base em onde ele acredita ter a maior probabilidade de encontrar um Sharpe melhor.
* **O que Testa:** É ideal para **explotação** (refinamento). Como nosso backtest (`backtesting.py`) é lento, a Otimização Bayesiana é a ferramenta ideal, pois foi projetada para encontrar o melhor resultado possível no **menor número de iterações**. É perfeita para fazer o ajuste fino dos parâmetros das Bandas de Bollinger (`bbands_window`, `bbands_std`) e dos filtros (`trend_window`, `garch_lookback`).

## 5. Parâmetros-Alvo para Otimização

A otimização será aplicada aos parâmetros numéricos da `STRATEGY_CONFIG`, permitindo ao pesquisador encontrar a melhor combinação de:
* `bbands_window`
* `bbands_std`
* `trend_window` (para `use_trend_filter=True`)
* `garch_lookback` (para `garch_mode != 'off'`)
* `garch_weight_window` (para `garch_mode = 'weight'`)
* `garch_lower_q` / `garch_upper_q` (para `garch_mode = 'gate'`)