from datetime import datetime

# =============================================================================
# --- 1. PARÂMETROS DA PIPELINE E ATIVOS (ARQUITETURA MISTA) ---
# =============================================================================

# Defina cada ativo como uma tupla: (TICKER, FONTE)
# Fontes válidas: 'mt5' ou 'yfinance'

# --- Exemplo de Ativos Individuais ---
Y_ASSET_DOL = ('DOL$', 'mt5')  # Contrato dólar
X_ASSET_MINIDOL = ('WDO$', 'mt5')       # Mini Dólar Futuro (contínuo) do MT5

Y_ASSET_BGI = ('BGI$', 'mt5')
X_ASSET_CCM = ('CCM$', 'mt5')

Y_ASSET_SUZB3 = ('SUZB3', 'mt5')
X_ASSET_KLBN11 = ('KLBN11', 'mt5')


# --- Lista de Pares para Analisar ---
# Agora é uma lista de tuplas, onde cada elemento é um ativo (ticker, fonte)
ASSET_PAIRS_TO_ANALYZE = [
    # O par misto que você queria:
    (Y_ASSET_DOL, X_ASSET_MINIDOL),
    
    # Um par puro do YFinance:
    (Y_ASSET_BGI, X_ASSET_CCM),
    
    # Um par puro do MT5:
    (Y_ASSET_SUZB3, X_ASSET_KLBN11)
]

# --- Benchmarks (também granulares) ---
BENCHMARK_TICKERS = [
    ('^BVSP', 'yfinance'), # Ibovespa do YFinance
    ('WIN$', 'mt5'),      # Mini-Índice do MT5
]

# =============================================================================
# --- 2. PARÂMETROS DE PERÍODO E TIMEFRAME ---
# =============================================================================
# Período para download dos dados históricos

data_inicio = datetime(2020, 1, 1)
data_fim = datetime(2025, 10, 1)

# Timeframe dos candles a serem baixados do MetaTrader 5
# Opções comuns: "M1", "M5", "M15", "M30", "H1", "D1"
timeframe = "D1"


# =============================================================================
# --- 3. PARÂMETROS DE VALIDAÇÃO ESTATÍSTICA ---
# =============================================================================
# Para usar este dicionário, modificar o 'validation.py'

VALIDATION_CONFIG = {
    'ADF_P_VALUE_THRESHOLD': 0.05,
    'KPSS_P_VALUE_THRESHOLD': 0.05,
    'COINT_P_VALUE_THRESHOLD': 0.05,
    'HURST_THRESHOLD': 0.5
}

# =============================================================================
# --- 4. PARÂMETROS DA ESTRATÉGIA DE TRADING ---
# =============================================================================
# Este é o "painel de controle" para ligar/desligar os filtros do Repo 1

STRATEGY_CONFIG = {
    # --- Os "Interruptores" ---
    "use_trend_filter": False,
    
    # --- NOVO INTERRUPTOR GARCH ---
    # Opções: 
    # 'off' (ignora GARCH, peso=1.0)
    # 'gate' (usa o filtro binário 0/1)
    # 'weight' (usa a ponderação 0.5-1.5)
    "garch_mode": "off", 

    # (O resto dos parâmetros de bbands, trend, garch...)
    "garch_weight_window": 252, # Nova janela para o Z-Score da volatilidade
    # --- Parâmetros dos Indicadores (do Repo 1) ---
    "bbands_window": 30,
    "bbands_std": 1.0,
    "trend_window": 90, # Janela da SMA longa (filtro de tendência)
    
    # --- Parâmetros do GARCH (do Repo 1) ---
    "garch_lookback": 252, # Janela rolante para treinar o GARCH
    "garch_lower_q": 0.05, # Quantil inferior de volatilidade
    "garch_upper_q": 0.95, # Quantil superior de volatilidade
    
    # --- Lógica de Saída (do Repo 2) ---
    # 'flip': Sai no extremo OPOSTO (ex: entra em -2, sai em +2).
    # 'zero_cross': Sai quando o Z-Score cruza a MÉDIA (Z-Score = 0).
    "exit_strategy": "zero_cross"
}

# =============================================================================
# --- 5. PARÂMETROS GERAIS DO BACKTEST ---
# =============================================================================

BACKTEST_CONFIG = {
    # Parâmetros de Tempo e Janela
    "formation_months": 6,  
    "trading_days_per_month": 21,
    "trading_hours_per_day": 8, # 8h p/ B3, 24h p/ FX/Crypto

    # Parâmetros de Simulação de Portfólio
    "initial_capital": 100000.0,
    "trade_size_pct": 1.0, # Usar 100% do capital
    "short_rental_fee_annual": 0.02 # 2% ao ano
}