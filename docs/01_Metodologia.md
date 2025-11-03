# Metodologia Estatística

O núcleo deste framework se baseia na identificação e exploração de relações de equilíbrio de longo prazo, ou estacionariedade, entre ativos. A seguir, detalhamos os métodos estatísticos empregados.

## 1. Teste de Cointegração (Engle-Granger)

O primeiro método de validação é o processo de duas etapas de Engle-Granger (EG).

1.  **Pré-Filtro (ADF Individual):** Antes de testar o par, aplicamos o teste de Dickey-Fuller Aumentado (ADF) em cada ativo individualmente. Se *qualquer* um dos ativos já for estacionário (p-valor < 0.05), o par é descartado, pois a cointegração requer que ambos sejam não-estacionários (integrados de ordem 1, I(1)).

2.  **Regressão OLS:** Uma regressão linear é executada para estimar a relação de longo prazo. O coeficiente (β) nos dá o **Hedge Ratio**.

    $$Y_t = \alpha + \beta X_t + \epsilon_t$$

3.  **Teste de Raiz Unitária nos Resíduos:** Aplicamos o teste ADF sobre os resíduos ($\epsilon_t$), que representam o "spread".
    * **Hipótese Nula (H₀):** O *spread* possui raiz unitária (NÃO é estacionário).
    * **Resultado:** Se o p-valor for baixo (ex: < 0.05), rejeitamos a H₀ e concluímos que o par é **cointegrado**.

## 2. Testes de Robustez (KPSS e Hurst)

Como o teste EG pode ser frágil, aplicamos testes de robustez adicionais. Crucialmente, estes testes são aplicados ao *spread* (calculado via OLS) **independentemente do resultado do teste EG**, para capturar pares que o EG possa ter perdido.

### Teste KPSS
O teste Kwiatkowski–Phillips–Schmidt–Shin (KPSS) é complementar ao ADF.
* **Hipótese Nula (H₀):** O *spread* **É** estacionário.
* **Resultado:** Procuramos um p-valor **alto** (ex: > 0.05) para *não* rejeitar a H₀, o que é uma forte evidência de estacionariedade.

### Expoente de Hurst (H)
O expoente de Hurst mede a "memória" de longo prazo de uma série.
* **$H = 0.5$**: Indica um passeio aleatório (Random Walk).
* **$H > 0.5$**: Indica persistência ou tendência (momentum).
* **$H < 0.5$**: Indica anti-persistência ou **reversão à média**.
* **Resultado:** Procuramos pares com **Hurst < 0.5**.

### Indicador `is_stationary_robust`
Combinamos os testes de robustez em um único indicador booleano para filtragem final:
* **`True`** se `p-valor KPSS > 0.05` **E** `Hurst < 0.5`.
* **`False`** caso contrário.

## 3. Cálculo da Meia-Vida (Half-Life)

Para pares que *passam* no teste de cointegração EG (onde o conceito é estatisticamente mais significativo), calculamos a **meia-vida de reversão à média**. Este valor estima o tempo médio para o *spread* reverter 50% do caminho de volta à sua média após um desvio.

Usamos a fórmula derivada do processo de Ornstein-Uhlenbeck:

$$\text{Meia-Vida} = \frac{\ln(2)}{-\gamma}$$

Onde $\gamma$ é o coeficiente de velocidade de reversão, obtido de uma regressão do *spread* contra sua própria defasagem.

## 4. Normalização do Spread (Z-Score)

Para gerar sinais, o *spread* bruto é normalizado. Embora a estratégia principal utilize Bandas de Bollinger (que são uma forma de Z-Score), o cálculo do Z-Score dinâmico (walk-forward) permanece central:

$$Z_t = \frac{\text{Spread}_t - \text{MédiaMóvel}(\text{Spread}_n)}{\text{DesvioPadrãoMóvel}(\text{Spread}_n)}$$

Isso nos diz quantos desvios-padrão o *spread* atual está afastado de sua média recente.