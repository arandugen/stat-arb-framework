import logging
import sys
import pandas as pd

import run_etl as run_etl
from run_validation import run_full_validation
from run_backtest import main_backtest
from run_validation import formatar_meia_vida

# --- CONFIGURAÇÃO CENTRALIZADA DO LOGGING ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    stream=sys.stdout # Garante que os logs apareçam no console
)

def main_pipeline():
    """
    Orquestra a execução de todo o pipeline do projeto de forma automatizada:
    1. Baixa e processa dados para todos os pares do config.
    2. Valida todos os pares para encontrar os cointegrados.
    3. Executa o backtest APENAS para os pares que passaram na validação.
    """
    logging.info("="*50)
    logging.info("--- INICIANDO PIPELINE AUTOMATIZADO COMPLETO ---")
    logging.info("="*50)
    
    # ETAPA 1 e 2: Coleta e Processamento dos Dados
    # Chamando as funções importadas diretamente
    run_etl.download_all_data(clean_dir=True)
    run_etl.process_all_data(clean_dir=True)

    # ETAPA 3: Validação Estatística de Todos os Pares
    logging.info("--- INICIANDO ETAPA 3: VALIDAÇÃO ESTATÍSTICA ---")
    validation_results_df = run_full_validation()
    logging.info("Relatório de Validação Completo salvo em 'validation_results.csv'")

    # ETAPA 4: Filtragem e Seleção de Pares Cointegrados
    logging.info("--- INICIANDO ETAPA 4: FILTRAGEM DE PARES COINTEGRADOS ---")
    cointegrated_pairs = validation_results_df[
        (validation_results_df['is_cointegrated'] == True) &
        (validation_results_df['status'] == 'Sucesso')
    ].copy() # Usar .copy() para evitar SettingWithCopyWarning
    
    if cointegrated_pairs.empty:
        logging.warning("Nenhum par cointegrado encontrado com os critérios definidos. Encerrando pipeline.")
        sys.exit(0)
    
    logging.info(f"Encontrados {len(cointegrated_pairs)} pares cointegrados para backtest:")
    
    # Mostra os pares cointegrados encontrados
    cointegrated_pairs['meia_vida'] = cointegrated_pairs['half_life_minutes'].apply(formatar_meia_vida)
    
    cointegrated_pairs['relationship_str'] = cointegrated_pairs['relationship'].apply(lambda x: '_'.join(x))
    
    # Adiciona as novas colunas para exibição
    colunas_para_mostrar = [
        'relationship_str', 'coint_p_value', 'kpss_p_value', 
        'hurst_exponent', 'is_stationary_robust', 'meia_vida'
    ]
    
    #    (Isso é robusto e evita erros se uma coluna não for encontrada)
    colunas_finais = [col for col in colunas_para_mostrar if col in cointegrated_pairs.columns]
    
    # 5. Imprime o resultado
    print(cointegrated_pairs[colunas_finais].to_string(index=False, float_format='%.4f'))


    # ETAPA 5: Backtesting em Lote para Pares Aprovados
    logging.info("--- INICIANDO ETAPA 5: BACKTESTING EM LOTE ---")

    for index, row in cointegrated_pairs.iterrows():
        pair_to_backtest = row['relationship']  # ('SUZB3', 'KLBN11'), por exemplo

        try:
            result = main_backtest(pair_to_backtest)

        except Exception as e:
            logging.error(f"Ocorreu um erro durante o backtest do par {pair_to_backtest}: {e}")
            continue  # Continua para o próximo par em caso de erro

    logging.info("="*50)
    logging.info("--- PIPELINE AUTOMATIZADO CONCLUÍDO COM SUCESSO ---")
    logging.info("="*50)

if __name__ == "__main__":
    main_pipeline()