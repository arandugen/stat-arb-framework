import os
import pandas as pd
import numpy as np
import logging

# (O config será importado pelo script que chamar esta função, como o manage_data.py)

def process_and_save_relationships(relationships_to_process: list, raw_path: str, processed_path: str):
    """
    Itera sobre uma lista de relações (pares/trios), carrega os dados brutos,
    processa-os (alinhamento, log) e salva o resultado na pasta 'processed'.

    Args:
        relationships_to_process (list): Lista de tuplas, cada uma contendo os tickers de uma relação.
        raw_path (str): Caminho para a pasta de dados brutos.
        processed_path (str): Caminho para a pasta onde os dados processados serão salvos.
    """
    logging.info("Iniciando o script de processamento de dados...")
    
    # Garante que o diretório de destino exista
    os.makedirs(processed_path, exist_ok=True)

    # Itera sobre cada relação (par ou trio)
    for relationship in relationships_to_process:
        
        output_filename = f"{'_'.join(relationship)}_log_prices.parquet"
        output_filepath = os.path.join(processed_path, output_filename)

        if os.path.exists(output_filepath):
            logging.info(f"Arquivo já existe, pulando processamento para: {output_filename}")
            continue

        logging.info(f"Processando relação: {relationship}")
        
        dataframes = []
        try:
            # Carrega os dados brutos para cada ticker na relação
            for ticker in relationship:
                file_path = os.path.join(raw_path, f"{ticker}.parquet")
                df_raw = pd.read_parquet(file_path)
                
                # Seleciona e renomeia a coluna 'close' imediatamente
                df_renamed = df_raw[['close']].rename(columns={'close': ticker})
                dataframes.append(df_renamed)
        
        except FileNotFoundError as e:
            logging.warning(f"Arquivo não encontrado para um dos tickers em {relationship}. Pulando este par. Detalhe: {e}")
            continue

        # Une todos os dataframes da lista (funciona para pares, trios, etc.)
        if len(dataframes) > 1:
            combined_df = pd.concat(dataframes, axis=1, join='inner')
        else:
            combined_df = dataframes[0]

        # Tratamento de dados faltantes
        combined_df.ffill(inplace=True)
        combined_df.dropna(inplace=True)

        if combined_df.empty:
            logging.warning(f"DataFrame vazio para {relationship} após alinhamento e limpeza. Pulando.")
            continue

        # Aplica a transformação logarítmica
        log_df = np.log(combined_df)

        # Salva o resultado final
        log_df.to_parquet(output_filepath)
        logging.info(f"Arquivo processado salvo com sucesso: {output_filename}")

    logging.info("Script de processamento de dados concluído.")

def align_and_merge_cdi(main_df: pd.DataFrame, cdi_df: pd.DataFrame, candles_per_day: int) -> pd.DataFrame:
    """
    Alinha o DataFrame do CDI (diário) ao índice do DataFrame principal
    (que pode ser intradiário) e calcula a taxa por candle.
    (Lógica movida de run_backtest.py)
    """
    logging.info("Alinhando e juntando dados do CDI para o backtest de caixa...")
    
    # 1. Alinha o índice do CDI (diário) ao índice do backtest
    cdi_aligned = cdi_df.reindex(main_df.index, method='ffill')
    
    # 2. Calcula a taxa *por candle*
    if candles_per_day > 0:
        cdi_aligned['cdi_rate'] = cdi_aligned['cdi_rate'] / candles_per_day
    else:
        cdi_aligned['cdi_rate'] = 0.0 # Segurança
        
    # 3. Junta a taxa ao DataFrame principal e preenche NaNs
    final_df = main_df.join(cdi_aligned['cdi_rate']).fillna(0.0)
    
    return final_df