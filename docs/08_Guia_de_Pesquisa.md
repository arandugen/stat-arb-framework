# 08. Guia de Pesquisa e Fluxos de Trabalho (Cookbook)

## 1. Visão Geral do Fluxo de Trabalho

Este documento é um guia prático (cookbook) que descreve os fluxos de trabalho (workflows) de pesquisa padrão usando o *framework*. Enquanto os documentos anteriores (`01-07`) descrevem *o que* o código é, este descreve *como* usá-lo.

O processo de pesquisa é dividido em quatro casos de uso principais:
1.  **Testar um Novo Par:** O fluxo completo, da ideia à validação.
2.  **Analisar a Sensibilidade:** O fluxo de *backtesting* rápido para testar variações de parâmetros.
3.  **Interpretar Relatórios:** Como ler os artefatos de saída gerados.
4.  **Estender a Estratégia:** Como adicionar novos filtros ao motor (guia de desenvolvedor).

## 2. Caso de Uso 1: Como Testar um Novo Par de Ativos

Este é o fluxo de trabalho para levar uma nova hipótese (ex: `BGI$ vs. CCM$`) do zero até a validação estatística.

### Passo 1: Definição da Hipótese (`config.py`)
1.  Abra o `config.py`.
2.  Na seção `ASSET_PAIRS_TO_ANALYZE`, adicione sua nova tupla de par. Você **deve** especificar o ticker e a fonte para cada "perna" do par.
    ```python
    # Exemplo: Adicionando um novo par
    Y_ASSET_BGI = ('BGI$', 'mt5')
    X_ASSET_CCM = ('CCM$', 'mt5')
    
    ASSET_PAIRS_TO_ANALYZE = [
        # ... (pares existentes)
        (Y_ASSET_BGI, X_ASSET_CCM) 
    ]
    ```

### Passo 2: Execução do Pipeline de ETL (`run_etl.py`)
Execute o orquestrador de ETL no terminal para baixar e processar os dados do novo par. O script é inteligente e só baixará os tickers que ainda não existem em `data/raw/`.

```bash
# 1. Baixa os dados brutos (ex: BGI$.parquet, CCM$.parquet)
python run_etl.py download

# 2. Processa os dados brutos (cria BGI$_CCM$_log_prices.parquet)
python run_etl.py process
````

  * **Output (Artefatos):** Novos arquivos em `data/raw/` e `data/processed/`.

### Passo 3: Execução da Validação (`run_validation.py`)

Execute o orquestrador de validação. Ele irá ler o `config.py`, encontrar seu novo par e aplicar os testes estatísticos (ADF, EG, KPSS, Hurst) nele.

```bash
python run_validation.py
```

  * **Output (Artefato):** O arquivo `validation_results.csv` será atualizado com os resultados do seu novo par.

### Passo 4: Análise de Viabilidade (`validation_results.csv`)

Abra o `validation_results.csv` e analise os resultados do seu par:

  * **`is_cointegrated`**: `True` se passou no teste de Engle-Granger.
  * **`is_stationary_robust`**: `True` se passou nos testes KPSS (p \> 0.05) **e** Hurst (H \< 0.5).

**Se `is_stationary_robust == True`, o par é um candidato forte para a estratégia de reversão à média.**

## 3\. Caso de Uso 2: Análise de Sensibilidade (Backtest Rápido)

Este é o fluxo de trabalho para testar como diferentes parâmetros da estratégia afetam um par que você **já validou** (ex: `SUZB3_KLBN11`).

### Passo 1: Alterar o Cenário (`config.py`)

Abra o `config.py` e modifique o `STRATEGY_CONFIG` para refletir sua nova hipótese.

**Exemplo:** Mudar do modo "Weight" para "Gate" no GARCH.

```python
# Em config.py -> STRATEGY_CONFIG
...
    # "garch_mode": "weight", # <-- Cenário Antigo
    "garch_mode": "gate",   # <-- Novo Cenário
...
```

### Passo 2: Executar o Orquestrador de Backtest (`run_backtest.py`)

Execute **apenas** o `run_backtest.py`, especificando o par com o argumento `--pair`. Isso é muito mais rápido do que rodar o `main_pipeline.py`, pois pula as etapas de ETL e Validação.

```bash
# Executa o backtest apenas para SUZB3 e KLBN11
python run_backtest.py --pair SUZB3 KLBN11
```

### Passo 3: Analisar os Relatórios (`reports/`)

O script irá gerar (e **sobrescrever**) os relatórios na pasta `reports/SUZB3_KLBN11/`. Compare os novos CSVs e gráficos com os resultados que você tinha antes da mudança no `config.py`.

*Aviso: Este fluxo manual sobrescreve resultados. Para uma análise de sensibilidade em lote, veja o `docs/09_Limitacoes_e_Roadmap.md`.*

## 4\. Caso de Uso 3: Como Interpretar a Pasta `/reports`

Cada execução do `run_backtest.py` (ou `main_pipeline.py`) gera uma subpasta em `/reports` (ex: `/reports/SUZB3_KLBN11/`) contendo os seguintes artefatos:

  * **`tabela_retornos_anuais.csv`:**

      * **O que é:** Performance de Retorno (CAGR) ano a ano, comparando a "Estratégia Híbrida" contra os benchmarks (Hedge Dinâmico, Buy & Hold, CDI).
      * **Como ler:** Permite identificar se a estratégia superou os benchmarks e em quais regimes de mercado (anos) ela foi melhor ou pior.

  * **`tabela_volatilidade_anual.csv`:**

      * **O que é:** Risco (Volatilidade Anualizada) ano a ano para a estratégia e benchmarks.
      * **Como ler:** Verifique se a `Estratégia Híbrida` atingiu seus retornos com uma volatilidade (risco) menor que os benchmarks.

  * **`curva_de_capital_comparativa.png`:**

      * **O que é:** O gráfico de crescimento do portfólio (Eixo Y) ao longo do tempo (Eixo X).
      * **Como ler:** A "prova visual" da performance. Procure por drawdowns severos. **Observe as "retas horizontais":** elas indicam períodos em que a estratégia estava em caixa. Graças à refatoração do `backtesting.py`, essas retas devem ter uma leve inclinação positiva, refletindo o rendimento do CDI.

  * **`indicadores_dinamicos.png`:**

      * **O que é:** Três gráficos de diagnóstico da estratégia.
      * **Como ler:**
          * **Gráfico 1 (Hedge Ratio):** Mostra a estabilidade do `hedge_ratio` (beta) ao longo do tempo.
          * **Gráfico 2 (Spread):** Mostra o *spread* (o "ativo sintético") e sua média.
          * **Gráfico 3 (Z-Score):** Mostra o *spread* normalizado. É útil para ver visualmente o quão "esticado" o *spread* fica, mesmo que a estratégia use Bandas de Bollinger para os sinais.

## 5\. Caso de Uso 4: Como Adicionar um Novo Filtro (Avançado)

Guia de desenvolvedor para estender a `STRATEGY_CONFIG` com um novo filtro (ex: um filtro de RSI).

1.  **Escrever a Lógica (a "Ferramenta"):**

      * Abra `src/indicators.py` e adicione sua nova função.
      * `def rsi(df: pd.DataFrame, window: int) -> pd.DataFrame:`
      * (A função deve calcular o RSI e adicionar a coluna `rsi` ao DataFrame).

2.  **Adicionar ao "Painel de Controle" (`config.py`):**

      * Abra `config.py` e adicione os novos parâmetros ao `STRATEGY_CONFIG`.
      * `"use_rsi_filter": True,`
      * `"rsi_window": 14,`
      * `"rsi_threshold": 30,`

3.  **Integrar à Estratégia (`strategy.py`):**

      * Abra `src/strategy.py` e modifique `generate_hybrid_signals`.
      * **a) Chame a função:**
        ```python
        if strategy_config["use_rsi_filter"]:
            logging.info("Aplicando Filtro de RSI...")
            df = indicators.rsi(df, window=strategy_config["rsi_window"])
        ```
      * **b) Use o resultado no loop `for`:**
        ```python
        for i in range(1, len(df)):
            # ... (cálculos de bullish, bearish, vol_ok) ...
            
            # Nova condição de filtro
            if strategy_config["use_rsi_filter"]:
                is_rsi_ok = df["rsi"].iloc[i] < strategy_config["rsi_threshold"]
            else:
                is_rsi_ok = True # Portão sempre aberto
                
            # Adicione 'is_rsi_ok' à lógica de entrada
            if position == 0 and is_bullish and is_vol_ok and is_rsi_ok and price < bb_low:
                # ... (entrar no trade) ...
        ```

