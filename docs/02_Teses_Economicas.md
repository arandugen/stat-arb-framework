# Teses Econômicas e Pares Candidatos

A seleção de pares para o teste de cointegração não é aleatória. Ela parte de hipóteses econômicas que justificam a existência de uma relação de equilíbrio de longo prazo entre os ativos.

## Hipóteses para Formação de Pares

A tabela abaixo resume as principais teses e os pares candidatos investigados neste projeto, com base no `README.md` original e nas pesquisas do framework.

| Par | Tese | Justificativa | Status (Preliminar) |
| :--- | :--- | :--- | :--- |
| **`ITUB4` vs. `BBDC4`** | Concorrência Direta | Maiores bancos privados do Brasil, expostos aos mesmos fatores macro (SELIC, inflação, inadimplência). | Não Cointegrado |
| **`AZUL4` vs. `GOLL4`** | Concorrência Direta | Principais companhias aéreas domésticas, sensíveis ao preço do combustível (QAV), câmbio e demanda. | Não Cointegrado |
| **`PETR4` vs. `PRIO3`** | Concorrência Direta | Produtoras de petróleo, cujas receitas são influenciadas pelo preço do Brent e pelo câmbio. | Não Cointegrado |
| **`ITSA4` vs. `ITUB4`** | Relação Estrutural | `ITSA4` é a holding controladora do `ITUB4`. O preço da holding é, em grande parte, uma função do preço de sua principal investida. | Não Cointegrado |
| **`VALE3` vs. `GGBR4`** | Cadeia Produtiva | `VALE3` (minério de ferro) é a principal fornecedora de insumo para a `GGBR4` (aço). | Não Cointegrado |
| **`SUZB3` vs. `KLBN11`**| Cadeia Produtiva | `SUZB3` (celulose) é insumo para a `KLBN11` (papel e embalagens). Ambas são grandes exportadoras. | **Cointegrado** |
| **`XPML11` vs. `HGLG11`**| Valor Relativo (FIIs) | FIIs de "tijolo" (Shoppings vs. Logística) expostos aos mesmos fatores macro (juros, PIB). | **Cointegrado** |
| **`BRL=X` vs. `DOL$`** | Relação Spot vs. Futuro (Acadêmica) | Testa a relação entre o preço Spot (indicativo do YFinance) e o contrato Futuro (executável da B3). A tese é que o *spread* representa o custo de carregamento, mas é uma hipótese com fragilidades de dados conhecidas (fontes distintas, não operável). | Não Cointegrado |
| **`BGI$` vs. `CCM$`** | Commodities Relacionadas | Relação entre os contratos futuros de Boi Gordo e Milho na B3, onde o milho é um insumo primário para a pecuária. | (Aguardando Teste) |

---

## Análise de Caso 1: SUZB3 vs. KLBN11

Este par, derivado da tese de Cadeia Produtiva, apresentou forte evidência de cointegração.

**Resultados da Validação (D1):**
* **p-valor (EG):** 0.0075
* **p-valor (KPSS):** 0.0177 (Falhou no teste de robustez)
* **Hurst:** 1.2771 (Indica tendência/persistência)
* **Meia-Vida:** ~28.3 dias

**Conclusão:** Embora seja cointegrado pelo teste EG, o *spread* não é estacionário (KPSS) e exibe forte tendência (Hurst), tornando-o um candidato ruim para a estratégia pura de reversão à média.

---

## Análise de Caso 2: XPML11 vs. HGLG11

Este par, da tese de Valor Relativo entre FIIs, também se mostrou cointegrado no teste EG.

**Resultados da Validação (D1):**
* **p-valor (EG):** 0.0292
* **p-valor (KPSS):** 0.0100 (Falhou no teste de robustez)
* **Hurst:** 1.2357 (Indica tendência/persistência)
* **Meia-Vida:** ~32.2 dias