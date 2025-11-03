import os
import sys
import logging
import pandas as pd
import numpy as np

# Adiciona a raiz do projeto ao path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

import config
from src import validation

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
        
        # Adiciona o par (só os nomes) para o processing.py
        pairs_for_processing.append((y_ticker, x_ticker))
        
    return pairs_for_processing

# --- FUNÇÕES AUXILIARES (EXISTENTES) ---
def parse_timeframe_to_minutes(timeframe_str: str) -> int:
    # (Lógica original inalterada)
    timeframe_str = timeframe_str.upper()
    try:
        if 'M' in timeframe_str:
            return int(timeframe_str.replace('M', ''))
        elif 'H' in timeframe_str:
            return int(timeframe_str.replace('H', '')) * 60
        elif 'D' in timeframe_str:
            return 8 * 60 # Assume 8h de pregão
        else:
            logging.warning(f"Formato de timeframe desconhecido: {timeframe_str}. Assumindo 0.")
            return 0
    except ValueError:
        logging.error(f"Não foi possível converter o timeframe '{timeframe_str}' para minutos.")
        return 0

def formatar_meia_vida(minutos: float) -> str:
    # (Lógica original inalterada)
    if pd.isna(minutos) or minutos <= 0:
        return ""
    horas = minutos / 60
    dias_de_pregao = horas / 8
    if dias_de_pregao < 2:
        return f"{horas:.1f} horas"
    return f"{dias_de_pregao:.1f} dias"


def run_full_validation() -> pd.DataFrame:
    """Executa a validação em lote e retorna o DF com a tupla original."""
    
    # --- CORREÇÃO ---
    # 1. Busca a lista de pares correta da nova função
    pairs_to_validate = get_pairs_for_validation()
    
    validation_results = []
    
    if not pairs_to_validate:
        logging.warning("Nenhuma lista de pares encontrada para validar. Verifique config.py.")
        return pd.DataFrame()
        
    logging.info(f"Iniciando validação para {len(pairs_to_validate)} relações (config mista).")

    # 2. Itera sobre a lista de pares correta
    for relationship in pairs_to_validate:
        # 'relationship' agora é ('BRL=X', 'DOL$'), por exemplo
        file_name = f"{'_'.join(relationship)}_log_prices.parquet"
        file_path = os.path.join(processed_data_path, file_name)
        
        result_dict = {
            'relationship': relationship,
            'status': 'Pendente',
            'coint_p_value': np.nan,
            'is_cointegrated': False,
            'half_life_minutes': np.nan,
            # (Adiciona as novas colunas para garantir que existam)
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
            freq_minutes = parse_timeframe_to_minutes(config.timeframe)
            if freq_minutes > 0:
                # Chama o módulo de validação
                output = validation.validate_pair_engle_granger(
                    df_processed, 
                    freq_minutes,
                    config.VALIDATION_CONFIG # <-- Passando o config
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
    
    # (Lógica de salvamento - JÁ ATUALIZADA)
    df_to_save = results_df.copy()
    df_to_save['meia_vida'] = df_to_save['half_life_minutes'].apply(formatar_meia_vida)
    # Converte a tupla ('BRL=X', 'DOL$') para a string 'BRL=X_DOL$'
    df_to_save['relationship'] = df_to_save['relationship'].apply(lambda x: '_'.join(x))
    
    colunas_para_salvar = [
        'relationship', 'status', 'coint_p_value', 'is_cointegrated', 
        'kpss_p_value', 'hurst_exponent', 'is_stationary_robust', 'meia_vida'
    ]
    df_to_save[colunas_para_salvar].to_csv(output_file, index=False, float_format='%.4f')
    logging.info(f"Arquivo CSV de resultados formatado salvo em: {output_file}")
    
    return results_df


if __name__ == "__main__":
    results = run_full_validation()
    
    if not results.empty:
        print("\n--- Resultado da Validação Estatística ---\n")
        
        # (Lógica de print)
        results['meia_vida'] = results['half_life_minutes'].apply(formatar_meia_vida)
        results['relationship_str'] = results['relationship'].apply(lambda x: '_'.join(x))
        
        colunas_para_mostrar = [
            'relationship_str', 'coint_p_value', 'kpss_p_value', 
            'hurst_exponent', 'is_stationary_robust', 'meia_vida'
        ]
        
        colunas_finais = [col for col in colunas_para_mostrar if col in results.columns]
        
        print(results[colunas_finais].to_string(index=False, float_format='%.4f'))
    else:
        print("\nNenhum resultado de validação para exibir.")