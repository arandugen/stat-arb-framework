import logging
import sys
import pandas as pd

# 1. Importa os orquestradores-filhos
import run_etl as run_etl
from run_validation import run_full_validation
from run_backtest import main_backtest

# 2. Importa as funções de "trabalho" da biblioteca src/
from src import validation
from src import reporting
from src import utils

# --- CONFIGURAÇÃO CENTRALIZADA DO LOGGING ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    stream=sys.stdout
)

def main_pipeline():
    """
    Orquestra a execução de todo o pipeline do projeto de forma automatizada.
    """
    logging.info("="*50)
    logging.info("--- INICIANDO PIPELINE AUTOMATIZADO COMPLETO ---")
    logging.info("="*50)
    
    # ETAPA 1 e 2: Orquestra o ETL
    run_etl.download_all_data(clean_dir=True)
    run_etl.process_all_data(clean_dir=True)

    # ETAPA 3: Orquestra a Validação
    logging.info("--- INICIANDO ETAPA 3: VALIDAÇÃO ESTATÍSTICA ---")
    validation_results_df = run_full_validation()
    logging.info("Relatório de Validação Completo salvo em 'validation_results.csv'")

    # ETAPA 4: Orquestra a Filtragem e o Resumo
    logging.info("--- INICIANDO ETAPA 4: FILTRAGEM DE PARES APROVADOS ---")
    
    approved_pairs_df = validation.filter_valid_pairs(validation_results_df)

    reporting.print_validation_summary(approved_pairs_df)
    
    if approved_pairs_df.empty:
        logging.warning("Nenhum par aprovado para backtest. Encerrando pipeline.")
        sys.exit(0)

    # ETAPA 5: Orquestra o Backtesting em Lote
    logging.info("--- INICIANDO ETAPA 5: BACKTESTING EM LOTE ---")

    for index, row in approved_pairs_df.iterrows():
        pair_to_backtest = row['relationship']
        
        try:
            result = main_backtest(pair_to_backtest)

        except Exception as e:
            logging.error(f"Ocorreu um erro durante o backtest do par {pair_to_backtest}: {e}")
            continue

    logging.info("="*50)
    logging.info("--- PIPELINE AUTOMATIZADO CONCLUÍDO COM SUCESSO ---")
    logging.info("="*50)

if __name__ == "__main__":
    main_pipeline()