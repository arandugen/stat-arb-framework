import pandas as pd

def sma(df: pd.DataFrame, window: int, column: str = "Close", output_col: str = None) -> pd.DataFrame:
    """Calcula a Média Móvel Simples com nome de coluna de saída customizável."""
    if output_col is None:
        output_col = f"SMA_{window}"
    
    df[output_col] = df[column].rolling(window=window).mean()
    return df

def trend_sma(df: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    """Calcula a Média Móvel de Tendência."""
    df[f"trend"] = df["Close"].rolling(window=window).mean()
    return df

def bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: int = 2) -> pd.DataFrame:
    """Calcula as Bandas de Bollinger."""
    rolling_mean = df["Close"].rolling(window).mean()
    rolling_std = df["Close"].rolling(window).std()

    df["BB_middle"] = rolling_mean
    df["BB_upper"] = rolling_mean + num_std * rolling_std
    df["BB_lower"] = rolling_mean - num_std * rolling_std
    return df