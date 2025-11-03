import os
import sys
import logging
import pandas as pd
import numpy as np


project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

import config
from src import validation
from src import utils
from src import reporting

# --- CONFIGURAÇÃO --
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
processed_data_path = os.path.join(project_root, 'data', 'processed')
output_file = os.path.join(project_root, 'validation_results.csv')

def get_pairs_for_validation() -> list:
    """
    Lê o config.ASSET_PAIRS_TO_ANALYZE (estrutura mista) e retorna
    uma lista de tuplas de pares (apenas os nomes) para validação.
    """
    pairs_for_processing = []
    
    for (y_asset, x_asset) in config.ASSET_PAIRS_TO_ANALYZE:
        y_ticker, y_source = y_asset
        x_ticker, x_source = x_asset
        
        pairs_for_processing.append((y_ticker, x_ticker))
        
    return pairs_for_processing

def run_full_validation() -> pd.DataFrame:
    """Executa a validação em lote e retorna o DF com a tupla original."""
    
    pairs_to_validate = get_pairs_for_validation()
    
    validation_results = []
    
    if not pairs_to_validate:
        logging.warning("Nenhuma lista de pares encontrada para validar. Verifique config.py.")
        return pd.DataFrame()
        
    logging.info(f"Iniciando validação para {len(pairs_to_validate)} relações (config mista).")

    for relationship in pairs_to_validate:
        file_name = f"{'_'.join(relationship)}_log_prices.parquet"
        file_path = os.path.join(processed_data_path, file_name)
        
        result_dict = {
            'relationship': relationship,
            'status': 'Pendente',
            'adf_p_value_Y': np.nan, 
            'adf_p_value_X': np.nan, 
            'coint_p_value': np.nan,
            'is_cointegrated': False,
            'half_life_minutes': np.nan,
            'kpss_p_value': np.nan,
            'hurst_exponent': np.nan,
            'is_stationary_robust': False
        }

        if not os.path.exists(file_path):
            result_dict.update({'status': 'Arquivo não encontrado'})
            validation_results.append(result_dict)
            logging.warning(f"Arquivo não encontrado: {file_name}. Pulando.")
            continue

        df_processed = pd.read_parquet(file_path)
        
        if len(relationship) == 2:
            time_params = utils.calculate_time_parameters(
                config.timeframe, 
                config.BACKTEST_CONFIG.get('trading_hours_per_day', 8)
            )
            freq_minutes = time_params['freq_in_minutes']
            
            if freq_minutes > 0:
                output = validation.validate_pair_engle_granger(
                    df_processed, 
                    freq_minutes,
                    config.VALIDATION_CONFIG
                ) 
                result_dict.update(output)
            else:
                result_dict.update({'status': 'Erro no Timeframe'})
        else:
            result_dict.update({'status': 'Não suportado (apenas pares)'}) 
            
        validation_results.append(result_dict)

    logging.info("Validação concluída.")
    
    if not validation_results:
        logging.warning("Nenhum resultado de validação foi gerado.")
        return pd.DataFrame()

    results_df = pd.DataFrame(validation_results)
    
    if 'coint_p_value' in results_df.columns:
        results_df.sort_values(by='coint_p_value', ascending=True, inplace=True)
    
    df_to_save = results_df.copy()
    
    df_to_save.to_csv(output_file, index=False, float_format='%.4f')
    logging.info(f"Arquivo CSV de resultados brutos salvo em: {output_file}")
    
    return results_df


if __name__ == "__main__":
   
    results_df = run_full_validation()
    
    if not results_df.empty:
        print("\n--- Resultado da Validação Estatística ---\n")
        
        valid_pairs_df = validation.filter_valid_pairs(results_df)
        
        reporting.print_validation_summary(valid_pairs_df)
    else:
        print("\nNenhum resultado de validação para exibir.")