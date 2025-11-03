# Framework de Pesquisa para Estratégias de Cointegração Híbridas na B3

## Descrição

Este repositório contém um framework completo e automatizado em Python para a pesquisa, validação e backtesting de estratégias de trading quantitativo baseadas em **cointegração**.

O projeto unifica duas abordagens de pesquisa:
1.  **Análise de Pares (StatArb):** Identificação de relações de equilíbrio de longo prazo entre ativos (ex: `SUZB3` vs. `KLBN11`).
2.  **Estratégias Híbridas:** Aplicação de modelos avançados (Bollinger, Filtros de Tendência, GARCH) sobre o *spread* do par, que é tratado como um ativo sintético.

## Funcionalidades Principais

* **Pipeline de Dados Flexível:** Coleta dados de múltiplas fontes (`MetaTrader 5` e `yfinance`) e permite a análise de pares com fontes mistas (ex: Spot do YFinance vs. Futuro do MT5).
* **Validação Estatística Robusta:** Utiliza um pipeline de validação que testa os pares não apenas com **Engle-Granger**, mas também com testes de robustez como **KPSS** e **Expoente de Hurst**.
* **Estratégia Híbrida Modular:** O motor de sinais (`strategy.py`) permite a configuração de estratégias complexas através de "interruptores" no `config.py`, combinando:
    * **Sinais de Entrada:** Bandas de Bollinger sobre o spread.
    * **Filtro de Tendência:** Uma SMA longa opcional para filtrar regimes (`use_trend_filter: True/False`).
    * **Filtro/Ponderação de Volatilidade:** Um filtro GARCH(1,1) que pode atuar como um "portão" (`garch_mode: 'gate'`) ou como um "ponderador" de posição (`garch_mode: 'weight'`).
* **Motor de Backtest Realista:** A simulação (`backtesting.py`) é iterativa (candle-a-candle) e incorpora:
    * **Juros Compostos:** O tamanho da posição é rebalanceado com base no capital atual.
    * **Custos Operacionais:** Simulação do custo de aluguel (BTC) para posições vendidas.
    * **Rendimento de Caixa (CDI):** O capital não alocado (em caixa) rende a taxa CDI diária, fornecendo um benchmark de custo de oportunidade mais justo.
* **Otimização de Parâmetros:** Incluirá futuramente um módulo (`optimizer.py`) com `differential_evolution` para a busca de parâmetros ótimos.

## Estrutura do Projeto

A estrutura atual é plana, com os módulos de lógica dentro de `src/` e os scripts orquestradores na raiz.

```

/stat-arb-framework/
│
├── data/                 \# Dados brutos e processados
│   ├── raw/
│   └── processed/
│
├── docs/                 \# Documentação detalhada da metodologia
│
├── reports/              \# Saída dos backtests (gráficos e CSVs)
│
├── src/                  \# Código fonte da biblioteca (o "motor")
│   ├── **init**.py
│   ├── backtesting.py
│   ├── benchmarks.py
│   ├── data_collection.py
│   ├── indicators.py
│   ├── models.py
│   ├── optimizer.py
│   ├── processing.py
│   ├── reporting.py
│   ├── strategy.py
│   ├── utils.py
│   └── validation.py
│
├── .env                  \# Arquivo para credenciais (NÃO COMMITAR)
├── .gitignore
├── config.py             \# Arquivo de configuração central
├── run_etl.py        \# Orquestrador do pipeline de ETL (Download/Processamento)
├── main_pipeline.py      \# Orquestrador principal (Roda tudo: ETL -\> Validação -\> Backtest)
├── run_backtest.py       \# Script para rodar um backtest em um único par
├── run_validation.py     \# Script para rodar apenas a validação
└── README.md             \# Este arquivo

````

## Como Usar

### 1. Configuração do Ambiente
O projeto usa `pip` e `venv` para gerenciamento de dependências.

```bash
# 1. Clone o repositório e navegue até a pasta
cd stat-arb-framework

# 2. Crie o ambiente virtual
python -m venv .venv

# 3. Ative o ambiente
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 4. Instale os pacotes
pip install -r requirements.txt
````

### 2\. Configuração do MetaTrader 5 (Arquivo .env)

Para coletar dados do MT5, crie um arquivo `.env` na raiz do projeto com suas credenciais:

```
# Credenciais de acesso para o MetaTrader 5
MT5_LOGIN=seu_login_mt5
MT5_PASSWORD=sua_senha_mt5
MT5_SERVER=nome_do_servidor_da_corretora
```

### 3\. Configurando o Pipeline (`config.py`)

Antes de executar, ajuste o `config.py` para definir sua pesquisa:

1.  **`ASSET_PAIRS_TO_ANALYZE`:** Defina os pares e suas fontes (`'mt5'` ou `'yfinance'`).
2.  **`STRATEGY_CONFIG`:** Ajuste os "interruptores" (`use_trend_filter`, `garch_mode`, `exit_strategy`) e os parâmetros (janelas, std).
3.  **`BACKTEST_CONFIG`:** Defina o capital, taxas, etc.

### 4\. Executando o Pipeline

Você pode executar o pipeline de ponta-a-ponta ou em partes.

```bash
# Opção 1: Executar o pipeline completo (ETL -> Validação -> Backtest)
python main_pipeline.py

# Opção 2: Executar apenas o ETL (Download e Processamento)
python run_etl.py download --clean
python run_etl.py process

# Opção 3: Executar apenas a Validação (pressupõe que os dados existem)
python run_validation.py

# Opção 4: Executar um backtest único (pressupõe que os dados existem)
python run_backtest.py --pair SUZB3 KLBN11
```

## Documentação

O *framework* é extensivamente documentado. Cada módulo e decisão de design é detalhado na pasta `/docs`.

* **[01 - Metodologia Estatística](docs/01_Metodologia.md)**
    * Explica os testes estatísticos usados na validação (ADF, Engle-Granger, KPSS, Hurst) e o cálculo da Meia-Vida.

* **[02 - Teses Econômicas e Pares Candidatos](docs/02_Teses_Economicas.md)**
    * Detalha as hipóteses econômicas (ex: Concorrência Direta, Cadeia Produtiva) para a seleção de pares e os resultados da validação preliminar.

* **[03 - Metodologia da Estratégia Híbrida](docs/03_Estrategia_Hibrida.md)**
    * Um guia técnico sobre a estratégia principal, detalhando os módulos (Bollinger, Trend, GARCH) e os "interruptores" de configuração.

* **[04 - Metodologia do Motor de Backtest](docs/04_Motor_Backtest.md)**
    * Pormenores do motor de simulação iterativo (`backtesting.py`), incluindo Juros Compostos, Custo de Aluguel (BTC) e Rendimento de Caixa (CDI).

* **[05 - Guia de Configuração (config.py)](docs/05_Guia_de_Configuracao.md)**
    * Um manual de referência detalhado para *cada* parâmetro no `config.py`, explicando seu impacto técnico no *pipeline*.

* **[06 - Guia de Execução e Orquestradores](docs/06_Guia_de_Execucao_e_Orquestradores.md)**
    * Detalha a arquitetura do *pipeline* (Biblioteca `src/` vs. Orquestradores) e os diferentes fluxos de trabalho (ex: `main_pipeline.py` vs. `run_backtest.py`).

* **[07 - Otimização de Parâmetros (Roadmap)](docs/07_Otimizacao_de_Parametros.md)**
    * Descreve a implementação futura do `optimizer.py`, focando na maximização do Sharpe Ratio e nas diferenças entre Evolução Diferencial e Otimização Bayesiana.

* **[08 - Guia de Pesquisa (Cookbook)](docs/08_Guia_de_Pesquisa.md)**
    * Um "manual do usuário" prático com fluxos de trabalho passo a passo para testar novos pares, fazer análises de sensibilidade e interpretar relatórios.

* **[09 - Limitações e Roadmap Futuro](docs/09_Limitacoes_e_Roadmap.md)**
    * Um relatório técnico sobre as limitações metodológicas (ex: Risco de Fonte de Dados) e o *roadmap* para funcionalidades futuras (Otimização, Refatoração, etc.).