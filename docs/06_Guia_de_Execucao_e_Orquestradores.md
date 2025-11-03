# 06. Guia de Execução e Arquitetura do Pipeline

Este documento detalha o design de infraestrutura do *framework*, focando na separação de responsabilidades entre a biblioteca de código (`src/`) e os scripts orquestradores (na raiz do projeto).

## 1. Filosofia de Design: Biblioteca vs. Orquestradores

O projeto é arquitetado em dois componentes distintos para garantir modularidade, manutenibilidade e flexibilidade na pesquisa:

### 1.1. A Biblioteca (O "Motor"): `src/`
A pasta `src/` contém a biblioteca de lógica de negócios do projeto. Nenhum arquivo dentro de `src/` deve ser executado diretamente. Eles apenas definem as "ferramentas" (funções e classes) que os orquestradores utilizam.

* `data_collection.py`: Define *como* baixar dados do MT5 e YFinance.
* `processing.py`: Define *como* alinhar e transformar pares.
* `validation.py`: Define *como* executar testes estatísticos (EG, KPSS, Hurst).
* `strategy.py`: Define *como* calcular o *spread* e os sinais híbridos (Bollinger, GARCH, Trend).
* `backtesting.py`: Define *como* simular o P&L de uma estratégia de forma iterativa.
* `reporting.py`: Define *como* calcular métricas e gerar relatórios.
* `utils.py`: Define "ferramentas" auxiliares (cálculo de tempo, limpeza).

### 1.2. Os Orquestradores (O "Volante"): `root/*.py`
Os scripts `.py` na pasta raiz do projeto são os "pontos de entrada" executáveis. Eles não contêm lógica de negócios, mas são responsáveis por:
1.  Ler o `config.py`.
2.  Chamar as funções da biblioteca `src/` na ordem correta.
3.  Lidar com o fluxo de dados (ler de um arquivo, passar para a biblioteca, salvar o resultado em outro arquivo).

Esta separação permite que o *pipeline* seja executado de forma modular. Por exemplo, o pesquisador pode optar por rodar apenas o ETL sem rodar o backtest, ou rodar o backtest de um único par sem re-baixar todos os dados.

## 2. O Fluxo de Dados (Data Flow)

A infraestrutura é baseada em "artefatos" de dados (arquivos `.parquet` e `.csv`) que atuam como as interfaces de comunicação entre os orquestradores.

O diagrama de fluxo de dados é o seguinte:

```graph TD
    A[config.py] --> B(run_etl.py);
    B --> C[data/raw/*.parquet];
    B --> D[data/processed/*.parquet];
    
    A --> E(run_validation.py);
    D --> E;
    E --> F[validation_results.csv];
    
    A --> G(run_backtest.py);
    C --> G;
    D --> G;
    
    H(main_pipeline.py) -.-> B;
    H -.-> E;
    F --> H;
    H -.-> G;
    
    G --> I[reports/PAR_X_Y/];
```

**Etapas do Fluxo:**

1.  **Configuração:** O `config.py` é lido por todos os orquestradores.
2.  **ETL (`run_etl.py`):** Lê `config.py` para saber *quais* pares baixar. Chama `data_collection.py` para salvar os dados brutos em `data/raw/` e `processing.py` para salvar os *spreads* logarítmicos em `data/processed/`.
3.  **Validação (`run_validation.py`):** Lê `config.py` para saber quais pares validar. Lê os arquivos de *spread* de `data/processed/`. Chama `validation.py` para executar os testes (EG, KPSS, Hurst). Salva os resultados em `validation_results.csv`.
4.  **Backtest (`run_backtest.py`):** Lê `config.py` para os parâmetros da estratégia (ex: `STRATEGY_CONFIG`) e do backtest (ex: `BACKTEST_CONFIG`). Lê os dados necessários de `data/raw/` (ex: CDI) e `data/processed/` (ex: *spreads*). Chama `strategy.py` e `backtesting.py` para rodar a simulação. Chama `reporting.py` para salvar os resultados em `reports/`.
5.  **Pipeline Mestre (`main_pipeline.py`):** Este é o orquestrador principal que executa as Etapas 2, 3 e 4 em sequência para um *pipeline* completo de ponta-a-ponta.

## 3\. Orquestradores e Casos de Uso

A infraestrutura decoupled permite diferentes fluxos de trabalho de pesquisa:

### `run_etl.py` (Orquestrador de ETL)

  * **Propósito:** Controlar o pipeline de Extração, Transformação e Carga de dados.
  * **Interface:** Linha de Comando (CLI).
  * **Caso de Uso 1: Baixar novos dados (ou atualizar existentes):**
    ```bash
    python run_etl.py download
    ```
  * **Caso de Uso 2: Re-processar dados brutos:**
    ```bash
    python run_etl.py process
    ```
  * **Caso de Uso 3: Limpar e re-executar todo o ETL:**
    ```bash
    python run_etl.py download --clean
    python run_etl.py process --clean
    ```

### `run_validation.py` (Orquestrador de Validação)

  * **Propósito:** Executar apenas os testes estatísticos nos dados processados.
  * **Caso de Uso: Testar novos parâmetros estatísticos:**
    Você alterou os limiares no `VALIDATION_CONFIG` e quer gerar um novo `validation_results.csv` sem re-baixar todos os dados.
    ```bash
    python run_validation.py
    ```

### `run_backtest.py` (Orquestrador de Simulação Única)

  * **Propósito:** Executar uma simulação completa para um **único par**.
  * **Interface:** Argumento de Linha de Comando (`--pair`).
  * **Caso de Uso: Análise de sensibilidade rápida:**
    Você já validou os pares e quer testar rapidamente o efeito de uma mudança no `STRATEGY_CONFIG` em um par específico, sem rodar o *pipeline* inteiro.
    ```bash
    # (Após mudar o config.py)
    python run_backtest.py --pair SUZB3 KLBN11
    ```

### `main_pipeline.py` (Orquestrador Mestre)

  * **Propósito:** Executar o fluxo de pesquisa completo do início ao fim.
  * **Caso de Uso: Execução Padrão (Full Run):**
    A execução padrão do projeto. O `processing.py` e `run_validation.py` são otimizados: o `processing.py` pula arquivos que já existem, e o `run_validation.py` (embora re-calcule) é rápido.
    ```bash
    python main_pipeline.py
    ```
