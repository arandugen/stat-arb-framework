# 09. Limitações Conhecidas e Roadmap Futuro

## 1. Visão Geral

Este documento detalha as limitações metodológicas e de implementação conhecidas do *framework* em seu estado atual. Ele também descreve o *roadmap* de desenvolvimento para futuras funcionalidades, visando aumentar o realismo e a robustez da pesquisa.

O *pipeline* principal está funcional, executando o fluxo de ETL, validação e backtest de ponta-a-ponta, e os *bugs* críticos de execução foram resolvidos.

## 2. Limitações Metodológicas e de Dados

Estas são limitações inerentes ao *design* atual ou aos dados utilizados.

### 2.1. Risco de Fonte de Dados (Indicativo vs. Executável)
A maior fragilidade metodológica do *framework* é a sua capacidade de misturar fontes de dados (ex: YFinance e MT5).

* **Problema:** Conforme identificado, dados do YFinance (ex: `BRL=X`) são *indicativos* (agregados) e não *operáveis*. Dados do MT5 (ex: `DOL$`) são *executáveis* (baseados no *book* da corretora).
* **Implicação:** A criação de um *spread* sintético entre essas duas fontes (`BRL=X_DOL$`) resulta em um ativo não operável.
* **Evidência:** Os testes estatísticos confirmam isso. O *spread* `BRL=X_DOL$` falhou em todos os testes de estacionariedade (p-valor do EG `> 0.5`, p-valor do KPSS `< 0.05`, e Expoente de Hurst `> 0.9`), indicando que ele não possui as propriedades de reversão à média necessárias para esta estratégia.

### 2.2. Cálculo do Spread (OLS)
O *spread* (resíduo) é atualmente calculado usando uma regressão OLS (Mínimos Quadrados Ordinários). Embora rápido e eficaz, o OLS é conhecido por sua sensibilidade a *outliers* (pontos de dados extremos), o que pode distorcer o `hedge_ratio` em janelas de dados voláteis.

### 2.3. Simulação de Custos de Transação
O motor de backtest (`backtesting.py`) é realista, mas incompleto em sua modelagem de custos:
* **Implementado:** Custo de aluguel (BTC) para posições vendidas (`short_rental_fee_annual`) e rendimento de caixa (CDI).
* **Não Implementado:** O motor atualmente não modela custos de corretagem (por ordem) nem *slippage* (derrapagem de preço), que é a diferença entre o preço do sinal e o preço real de execução. Isso faz com que os resultados de performance (CAGR, Sharpe) sejam superestimados.

## 3. Dívida Técnica e Decisões de Design

Decisões de engenharia tomadas para garantir a robustez ou que precisam de revisão futura.

* **`FutureWarning`s do Pandas:** O *pipeline* gera múltiplos `FutureWarning`s (ex: `Downcasting object...`, `chained assignment`), especialmente em `src/strategy.py` e `src/models.py`. Embora tenham sido feitas tentativas de correção (ex: usando `.astype(bool)`), eles persistem. Atualmente, são considerados avisos não-críticos de sintaxe, mas representam uma dívida técnica que deve ser resolvida para garantir a compatibilidade com o Pandas 3.0+.
* **Saída de Relatórios (CSV):** Para resolver erros persistentes de *styling* (`Cannot mask...`) na biblioteca `dataframe_image`, a saída das tabelas de relatório (`reporting.py`) foi padronizada para `.csv`. Esta decisão prioriza a **robustez** e a conclusão do *pipeline* em detrimento da estética do relatório.
* **Arquitetura `src/` Plana:** A pasta `src/` possui uma estrutura plana. Embora funcional, ela se tornará difícil de manter à medida que o projeto crescer.

## 4. Roadmap de Próximos Passos (Funcionalidades Futuras)

1.  **[P1] Implementação da Otimização de Parâmetros:**
    * **Meta:** Refatorar o `optimizer.py` para integrá-lo ao *pipeline* principal.
    * **Ações:**
        1.  Modificar a `objective_function` para que ela chame o motor realista (`backtesting.run_backtest`) em vez do simulador vetorizado `simulate_portfolio`.
        2.  Mudar a métrica-alvo de `final_portfolio_value` para `-sharpe_ratio`.
        3.  Implementar a Otimização Bayesiana como uma alternativa ao `differential_evolution`, conforme descrito no `docs/07_Otimizacao_de_Parametros.md`.

2.  **[P2] Orquestrador de Análise de Sensibilidade:**
    * **Meta:** Automatizar o processo manual de teste de cenários (descrito no `docs/08_Guia_de_Pesquisa.md`).
    * **Ações:** Criar um novo script orquestrador (`run_sensitivity_analysis.py`) que leia uma lista de cenários (diferentes `STRATEGY_CONFIG`s) e execute o `run_backtest.py` em lote para cada par validado.

3.  **[P3] Refinamento de Custos (Slippage e Corretagem):**
    * **Meta:** Aumentar o realismo do `backtesting.py`.
    * **Ações:** Adicionar parâmetros ao `BACKTEST_CONFIG` para `brokerage_fee_pct` e `slippage_pct`, e incorporá-los ao cálculo do P&L.

4.  **[P4] Refatoração da Arquitetura `src/`:**
    * **Meta:** Melhorar a manutenibilidade do código.
    * **Ações:** Reestruturar a pasta `src/` em subpacotes lógicos (ex: `src/data`, `src/strategy`, `src/backtesting`), conforme discutido.

5.  **[P5] Integração do Teste de Johansen:**
    * **Meta:** Habilitar a análise de cointegração para trios de ativos.
    * **Ações:**
        1.  A função `validate_trio_johansen` já existe em `src/validation.py`.
        2.  Modificar o `config.py` para aceitar trios (ex: `ASSET_TRIOS_TO_ANALYZE`).
        3.  Atualizar `run_validation.py` e `processing.py` para processar e testar essas tuplas de 3 elementos.