"""Market Dashboard configuration — all ticker definitions, categories, refresh intervals."""

from pathlib import Path

PORT = 8060

# ─── Refresh intervals (seconds) ───
# Asset pages download 10Y history for multi-period returns — keep intervals reasonable
REFRESH_INDICES = 120
REFRESH_FUTURES = 120
REFRESH_FOREX = 120
REFRESH_BONDS = 60
REFRESH_ECONOMY = 3600  # hourly
REFRESH_POLYMARKET = 120
REFRESH_NEWS = 120
REFRESH_CALENDAR = 300  # 5 min
REFRESH_MOVERS = 300    # 5 min
REFRESH_OPTIONS = 300   # 5 min

# ─── Polymarket ───
POLYMARKET_BIN = "/opt/homebrew/bin/polymarket"
POLYMARKET_EVENT_LIMIT = 15

# ─── World Indices ───
WORLD_INDICES = [
    # Americas
    {"symbol": "^GSPC",    "name": "S&P 500",       "region": "Americas",     "country": "United States"},
    {"symbol": "^DJI",     "name": "Dow Jones",      "region": "Americas",     "country": "United States"},
    {"symbol": "^IXIC",    "name": "Nasdaq",         "region": "Americas",     "country": "United States"},
    {"symbol": "^RUT",     "name": "Russell 2000",   "region": "Americas",     "country": "United States"},
    {"symbol": "^GSPTSE",  "name": "S&P/TSX",        "region": "Americas",     "country": "Canada"},
    {"symbol": "^BVSP",    "name": "Bovespa",        "region": "Americas",     "country": "Brazil"},
    # Europe
    {"symbol": "^FTSE",    "name": "FTSE 100",       "region": "Europe",       "country": "United Kingdom"},
    {"symbol": "^GDAXI",   "name": "DAX",            "region": "Europe",       "country": "Germany"},
    {"symbol": "^FCHI",    "name": "CAC 40",         "region": "Europe",       "country": "France"},
    {"symbol": "^STOXX50E","name": "Euro Stoxx 50",  "region": "Europe",       "country": "Eurozone"},
    {"symbol": "^IBEX",    "name": "IBEX 35",        "region": "Europe",       "country": "Spain"},
    {"symbol": "FTSEMIB.MI","name": "FTSE MIB",      "region": "Europe",       "country": "Italy"},
    # Asia-Pacific
    {"symbol": "^N225",    "name": "Nikkei 225",     "region": "Asia-Pacific", "country": "Japan"},
    {"symbol": "^TOPX",    "name": "TOPIX",          "region": "Asia-Pacific", "country": "Japan"},
    {"symbol": "^HSI",     "name": "Hang Seng",      "region": "Asia-Pacific", "country": "Hong Kong"},
    {"symbol": "000001.SS","name": "Shanghai",        "region": "Asia-Pacific", "country": "China"},
    {"symbol": "000300.SS","name": "CSI 300",         "region": "Asia-Pacific", "country": "China"},
    {"symbol": "^KS11",    "name": "KOSPI",          "region": "Asia-Pacific", "country": "South Korea"},
    {"symbol": "^AXJO",    "name": "ASX 200",        "region": "Asia-Pacific", "country": "Australia"},
    {"symbol": "^BSESN",   "name": "BSE Sensex",     "region": "Asia-Pacific", "country": "India"},
    {"symbol": "^NSEI",    "name": "NIFTY 50",       "region": "Asia-Pacific", "country": "India"},
    {"symbol": "^STI",     "name": "Straits Times",  "region": "Asia-Pacific", "country": "Singapore"},
    {"symbol": "^TWII",    "name": "TAIEX",          "region": "Asia-Pacific", "country": "Taiwan"},
    {"symbol": "^NZ50",    "name": "NZX 50",         "region": "Asia-Pacific", "country": "New Zealand"},
]

# ─── S&P Sector ETFs ───
SP_SECTORS = [
    {"symbol": "XLK",  "name": "Technology"},
    {"symbol": "XLF",  "name": "Financials"},
    {"symbol": "XLE",  "name": "Energy"},
    {"symbol": "XLV",  "name": "Health Care"},
    {"symbol": "XLI",  "name": "Industrials"},
    {"symbol": "XLC",  "name": "Communication"},
    {"symbol": "XLY",  "name": "Consumer Disc."},
    {"symbol": "XLP",  "name": "Consumer Staples"},
    {"symbol": "XLB",  "name": "Materials"},
    {"symbol": "XLRE", "name": "Real Estate"},
    {"symbol": "XLU",  "name": "Utilities"},
]

# ─── Defense & Aerospace Indexes ───
DEFENSE_INDEXES = [
    {"symbol": "ITA",  "name": "iShares U.S. Aerospace & Defense", "desc": "S&P 500 Aerospace & Defense Sub-Industry"},
    {"symbol": "XAR",  "name": "SPDR S&P Aerospace & Defense",    "desc": "S&P Aerospace & Defense Select Industry Index"},
    {"symbol": "PPA",  "name": "Invesco Aerospace & Defense",     "desc": "SPADE Defense Index"},
]

# ─── Futures ───
FUTURES = {
    "Currency": [
        {"symbol": "6E=F",  "name": "Euro FX"},
        {"symbol": "6B=F",  "name": "British Pound"},
        {"symbol": "6J=F",  "name": "Japanese Yen"},
        {"symbol": "6A=F",  "name": "Australian Dollar"},
        {"symbol": "6C=F",  "name": "Canadian Dollar"},
        {"symbol": "6S=F",  "name": "Swiss Franc"},
    ],
    "World Indices": [
        {"symbol": "ES=F",  "name": "S&P 500 E-mini"},
        {"symbol": "NQ=F",  "name": "Nasdaq E-mini"},
        {"symbol": "YM=F",  "name": "Dow E-mini"},
        {"symbol": "RTY=F", "name": "Russell E-mini"},
        {"symbol": "NIY=F", "name": "Nikkei 225"},
    ],
    "Interest Rates": [
        {"symbol": "ZT=F",  "name": "2-Year T-Note"},
        {"symbol": "ZF=F",  "name": "5-Year T-Note"},
        {"symbol": "ZN=F",  "name": "10-Year T-Note"},
        {"symbol": "ZB=F",  "name": "30-Year T-Bond"},
    ],
    "Shipping": [
        {"symbol": "BDRY",  "name": "Baltic Dry (ETF)"},
    ],
}

# ─── Forex ───
# Major currencies for the heatmap matrix
FOREX_CURRENCIES = ["EUR", "USD", "GBP", "AUD", "NZD", "CAD", "CHF", "JPY"]

# USD-based pairs for deriving all cross rates
FOREX_USD_PAIRS = {
    "EUR": "EURUSD=X",
    "GBP": "GBPUSD=X",
    "AUD": "AUDUSD=X",
    "NZD": "NZDUSD=X",
    "CAD": "USDCAD=X",  # inverted (USD/CAD)
    "CHF": "USDCHF=X",  # inverted (USD/CHF)
    "JPY": "USDJPY=X",  # inverted (USD/JPY)
}

# Pairs where USD is the quote currency (XXXUSD) — rate = units of USD per 1 XXX
FOREX_USD_QUOTE = {"EUR", "GBP", "AUD", "NZD"}
# Pairs where USD is the base currency (USDXXX) — rate = units of XXX per 1 USD
FOREX_USD_BASE = {"CAD", "CHF", "JPY"}

# All major pairs for the pairs table
FOREX_PAIRS = [
    {"symbol": "EURUSD=X",  "name": "EUR/USD"},
    {"symbol": "GBPUSD=X",  "name": "GBP/USD"},
    {"symbol": "USDJPY=X",  "name": "USD/JPY"},
    {"symbol": "USDCHF=X",  "name": "USD/CHF"},
    {"symbol": "AUDUSD=X",  "name": "AUD/USD"},
    {"symbol": "NZDUSD=X",  "name": "NZD/USD"},
    {"symbol": "USDCAD=X",  "name": "USD/CAD"},
    # Crosses
    {"symbol": "EURGBP=X",  "name": "EUR/GBP"},
    {"symbol": "EURJPY=X",  "name": "EUR/JPY"},
    {"symbol": "GBPJPY=X",  "name": "GBP/JPY"},
    {"symbol": "AUDJPY=X",  "name": "AUD/JPY"},
    {"symbol": "EURAUD=X",  "name": "EUR/AUD"},
    {"symbol": "EURCHF=X",  "name": "EUR/CHF"},
    {"symbol": "GBPCHF=X",  "name": "GBP/CHF"},
    {"symbol": "AUDNZD=X",  "name": "AUD/NZD"},
    {"symbol": "NZDJPY=X",  "name": "NZD/JPY"},
    {"symbol": "CADCHF=X",  "name": "CAD/CHF"},
    {"symbol": "CADJPY=X",  "name": "CAD/JPY"},
    # EM currencies
    {"symbol": "USDCNH=X",  "name": "USD/CNH"},
    {"symbol": "USDBRL=X",  "name": "USD/BRL"},
    {"symbol": "USDMXN=X",  "name": "USD/MXN"},
    {"symbol": "USDINR=X",  "name": "USD/INR"},
    {"symbol": "USDZAR=X",  "name": "USD/ZAR"},
    {"symbol": "USDTRY=X",  "name": "USD/TRY"},
]

# Heatmap period options (label → yfinance period/interval)
FOREX_HEATMAP_PERIODS = {
    "1D": {"period": "5d", "days_back": 1},
    "1W": {"period": "1mo", "days_back": 5},
    "1M": {"period": "3mo", "days_back": 21},
    "3M": {"period": "6mo", "days_back": 63},
    "YTD": {"period": "ytd", "days_back": None},  # calculated from Jan 1
    "1Y": {"period": "1y", "days_back": 252},
}

# ─── Bonds ───
# US Treasury yields available via yfinance
US_TREASURY_YIELDS = [
    {"symbol": "^IRX",  "name": "3-Month", "maturity": 0.25},
    # 2YY=F delisted — 2Y yield available via FRED (DGS2) on bonds page
    {"symbol": "^FVX",  "name": "5-Year",  "maturity": 5},
    {"symbol": "^TNX",  "name": "10-Year", "maturity": 10},
    {"symbol": "^TYX",  "name": "30-Year", "maturity": 30},
]

# Volatility indices
MOVE_INDEX = {"symbol": "^MOVE", "name": "MOVE Index", "desc": "ICE BofA Bond Volatility"}

# International yield curves are fetched directly from central bank sources
# (see app/sources/intl_bonds.py) — RBA, ECB, Japan MoF

# ─── Macro Pulse / HUD ───
PULSE_INDICATORS = [
    {"symbol": "DX-Y.NYB", "name": "DXY",      "desc": "US Dollar Index"},
    {"symbol": "^TNX",     "name": "US 10Y",    "desc": "10-Year Treasury Yield"},
    # 2YY=F removed — delisted
    {"symbol": "^VIX",     "name": "VIX",       "desc": "Equity Volatility"},
    {"symbol": "^MOVE",    "name": "MOVE",      "desc": "Bond Volatility (ICE BofA)"},
    {"symbol": "^GSPC",    "name": "S&P 500",   "desc": "US Large Cap"},
    {"symbol": "HG=F",     "name": "Copper",    "desc": "Industrial Bellwether"},
    {"symbol": "GC=F",     "name": "Gold",      "desc": "Safe Haven"},
    {"symbol": "CL=F",     "name": "WTI Oil",   "desc": "Energy / Inflation"},
    {"symbol": "BTC-USD",  "name": "Bitcoin",   "desc": "Crypto"},
]

# Commodity proxy ratios
COMMODITY_RATIOS = [
    {"numerator": "GC=F",  "denominator": "SI=F",  "name": "Gold/Silver",  "desc": "Risk sentiment — rising = defensive"},
    {"numerator": "HG=F",  "denominator": "GC=F",  "name": "Copper/Gold",  "desc": "Growth vs safety — rising = risk-on"},
]

# Sector rotation — compare sector ETFs vs SPY
ROTATION_SECTORS = [
    {"symbol": "XLK",  "name": "Tech"},
    {"symbol": "XLF",  "name": "Financials"},
    {"symbol": "XLE",  "name": "Energy"},
    {"symbol": "XLV",  "name": "Health Care"},
    {"symbol": "XLI",  "name": "Industrials"},
    {"symbol": "XLU",  "name": "Utilities"},
    {"symbol": "XLY",  "name": "Consumer Disc."},
    {"symbol": "XLP",  "name": "Consumer Staples"},
]

# ─── Economy — reference data ───
# Major economies with key indicators (updated periodically)
# Source: IMF/World Bank/Trading Economics — for display purposes
ECONOMY_COUNTRIES = [
    "USA", "China", "EU", "Germany", "Japan",
    "India", "UK", "France", "Canada", "Australia",
]

ECONOMY_INDICATORS = [
    "GDP ($T)", "GDP Growth", "Budget/GDP", "Govt Debt/GDP",
    "Interest Rate", "Inflation Rate", "Unemployment",
    "Current Acct/GDP", "Industrial Prod Y/Y",
]

# ─── Economy Historical (FRED series for time-series charts) ───
ECONOMY_HISTORICAL = {
    "GDP Growth (% QoQ)": {
        "USA":       "A191RL1Q225SBEA",
        "UK":        "NAEXKP06GBQ189S",
        "Japan":     "NAEXKP06JPQ189S",
        "Eurozone":  "NAEXKP06EZQ189S",
        "Australia": "NAEXKP06AUQ189S",
        "Canada":    "NAEXKP06CAQ189S",
    },
    "Inflation (% YoY)": {
        "USA":       "CPALTT01USM659N",
        "UK":        "CPALTT01GBM659N",
        "Japan":     "CPALTT01JPM659N",
        "Eurozone":  "EA19CPALTT01GYM",
        "Australia": "CPALTT01AUM659N",
        "Canada":    "CPALTT01CAM659N",
    },
    "Unemployment (%)": {
        "USA":       "UNRATE",
        "UK":        "LRHUTTTTGBM156S",
        "Japan":     "LRHUTTTTJPM156S",
        "Eurozone":  "LRHUTTTTEZM156S",
        "Australia": "LRHUTTTTAUM156S",
        "Canada":    "LRHUTTTTCAM156S",
    },
    "Interest Rate (%)": {
        "USA":       "FEDFUNDS",
        "UK":        "IUDSOIA",
        "Japan":     "IR3TIB01JPM156N",
        "Eurozone":  "ECBDFR",
        "Australia": "IRSTCI01AUM156N",
        "Canada":    "IR3TIB01CAM156N",
    },
}
REFRESH_ECONOMY_HISTORICAL = 21600  # 6 hours

# ─── News ───
GOOGLE_NEWS_QUERIES = [
    "breaking geopolitical news market impact",
    "federal reserve interest rate decision",
    "US China trade tariffs",
    "stock market breaking news today",
    "oil price breaking news",
    "crypto regulation breaking news",
]

GOOGLE_NEWS_RSS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# ─── Economic Calendar ───
FOREXFACTORY_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# ─── Market Movers ───
MOVERS_LIMIT = 10  # top N gainers/losers/active

# International exchange mappings for movers screener
MOVERS_EXCHANGES = {
    "US":        {"name": "United States", "exchange": None,  "currency": "$"},     # predefined screens
    "Australia": {"name": "Australia",     "exchange": "ASX", "currency": "A$"},
    "UK":        {"name": "United Kingdom","exchange": "LSE", "currency": "£"},
    "Europe":    {"name": "Europe",        "exchange": "GER", "currency": "€"},
    "Japan":     {"name": "Japan",         "exchange": "JPX", "currency": "¥"},
}

# ─── Central Bank Policy Rates (FRED) ───
CENTRAL_BANK_RATES = [
    {"series_id": "FEDFUNDS",  "name": "Fed Funds Rate",    "country": "USA",       "bank": "Federal Reserve"},
    {"series_id": "ECBDFR",    "name": "ECB Deposit Rate",  "country": "Euro Area", "bank": "ECB"},
    {"series_id": "IUDSOIA",   "name": "BoE Bank Rate",     "country": "UK",        "bank": "Bank of England"},
    {"series_id": "IR3TIB01JPM156N", "name": "Interbank Rate", "country": "Japan",  "bank": "Bank of Japan"},
    {"series_id": "IRSTCI01AUM156N", "name": "Policy Rate",    "country": "Australia", "bank": "RBA"},
    {"series_id": "IR3TIB01CAM156N", "name": "Policy Rate",    "country": "Canada",  "bank": "Bank of Canada"},
    {"series_id": "INTDSRCNM193N",   "name": "Lending Rate",   "country": "China",   "bank": "PBoC"},
    {"series_id": "IRSTCI01INM156N", "name": "Policy Rate",    "country": "India",   "bank": "RBI"},
]

# ─── VIX Term Structure ───
VIX_TERM_STRUCTURE = [
    {"symbol": "^VIX",   "name": "VIX (Spot)",   "tenor_days": 0},
    {"symbol": "^VIX9D", "name": "VIX 9-Day",    "tenor_days": 9},
    {"symbol": "^VIX3M", "name": "VIX 3-Month",  "tenor_days": 90},
    {"symbol": "^VIX6M", "name": "VIX 6-Month",  "tenor_days": 180},
]

# ─── Inflation Nowcast (Cleveland Fed via FRED) ───
INFLATION_NOWCAST_SERIES = [
    {"series_id": "EXPINF1YR",  "name": "1Y Expected Inflation", "unit": "%", "category": "expectations"},
    {"series_id": "EXPINF2YR",  "name": "2Y Expected Inflation", "unit": "%", "category": "expectations"},
    {"series_id": "EXPINF10YR", "name": "10Y Expected Inflation", "unit": "%", "category": "expectations"},
    {"series_id": "T5YIE",      "name": "5Y Breakeven Inflation", "unit": "%", "category": "market"},
    {"series_id": "T10YIE",     "name": "10Y Breakeven Inflation", "unit": "%", "category": "market"},
    {"series_id": "T5YIFR",     "name": "5Y5Y Forward Inflation", "unit": "%", "category": "market"},
    {"series_id": "MEDCPIM158SFRBCLE", "name": "Median CPI (Cleveland Fed)", "unit": "%", "category": "nowcast"},
    {"series_id": "TRMMEANCPIM158SFRBCLE", "name": "Trimmed Mean CPI (Cleveland Fed)", "unit": "%", "category": "nowcast"},
]

# ─── Commodities (analytical view by sector) ───
REFRESH_COMMODITIES = 120

COMMODITIES = {
    # ═══ ENERGY ═══
    "Energy": {
        "description": "Global energy complex; OPEC+ driven; inflation transmission",
        "market_lens": "OPEC+ policy, geopolitics, USD strength, demand cycles, energy transition.",
        "items": [
            {"symbol": "CL=F",  "name": "Crude Oil WTI",  "benchmark": "WTI",
             "drivers": "OPEC+ policy, geopolitics, USD strength, demand cycles"},
            {"symbol": "BZ=F",  "name": "Brent Crude",    "benchmark": "ICE Brent",
             "drivers": "OPEC+ policy, geopolitics, USD strength, demand cycles"},
            {"symbol": "NG=F",  "name": "Natural Gas",    "benchmark": "Henry Hub",
             "drivers": "Weather, LNG exports, storage levels, substitution"},
            {"symbol": "TTF=F", "name": "Dutch TTF Gas",  "benchmark": "ICE Endex",
             "drivers": "European demand, LNG cargo flows, storage, Russia supply risk"},
            {"symbol": "HO=F",  "name": "Heating Oil",    "benchmark": "NYMEX",
             "drivers": "Crude oil correlation, winter demand, refinery margins"},
            {"symbol": "RB=F",  "name": "RBOB Gasoline",  "benchmark": "NYMEX",
             "drivers": "Crude oil correlation, driving season demand, refinery utilisation"},
            {"symbol": "HNRG",  "name": "Coal (ETF)",     "benchmark": "SPI Energy Coal",
             "drivers": "Asian power demand, gas prices, renewables displacement"},
            {"symbol": "URA",   "name": "Uranium (ETF)",  "benchmark": "Global X Uranium",
             "drivers": "Nuclear policy cycles, long-term contracting, reactor restarts"},
        ],
    },

    # ═══ AGRICULTURAL ═══
    "Grains & Cereals": {
        "description": "Core global calorie staples; highly traded; benchmarked",
        "market_lens": "Acreage, yields, stocks to use, export competitiveness, weather sensitivity.",
        "items": [
            {"symbol": "ZC=F",  "name": "Corn (Maize)",   "benchmark": "CBOT",
             "drivers": "Ethanol demand, feed use, La Niña/El Niño"},
            {"symbol": "ZW=F",  "name": "Wheat",          "benchmark": "CBOT",
             "drivers": "Black Sea geopolitics, weather, food security policy"},
            {"symbol": "ZR=F",  "name": "Rice",           "benchmark": "CBOT",
             "drivers": "Asian demand, monsoon patterns, export restrictions"},
            {"symbol": "ZO=F",  "name": "Oats",           "benchmark": "CBOT",
             "drivers": "Feed demand, weather, alternative grain substitution"},
        ],
    },
    "Oilseeds & Vegetable Oils": {
        "description": "Protein + oil value; biofuels linkage",
        "market_lens": "Crush margins, veg oil substitution, biodiesel mandates, China demand.",
        "items": [
            {"symbol": "ZS=F",  "name": "Soybeans",       "benchmark": "CBOT",
             "drivers": "China crushing demand, Brazil/Argentina production"},
            {"symbol": "ZL=F",  "name": "Soybean Oil",    "benchmark": "CBOT",
             "drivers": "Biodiesel mandates, palm oil substitution, China demand"},
            {"symbol": "ZM=F",  "name": "Soybean Meal",   "benchmark": "CBOT",
             "drivers": "Feed demand, crush margins, livestock cycle"},
        ],
    },
    "Soft Commodities": {
        "description": "Weather, labour, geopolitics highly influential",
        "market_lens": "El Niño/La Niña, disease risk, export concentration, FX exposure.",
        "items": [
            {"symbol": "SB=F",  "name": "Sugar",          "benchmark": "ICE",
             "drivers": "Brazil ethanol parity, monsoon (India)"},
            {"symbol": "KC=F",  "name": "Coffee",         "benchmark": "ICE",
             "drivers": "Brazil/Vietnam crop cycles, FX, climate risk"},
            {"symbol": "CC=F",  "name": "Cocoa",          "benchmark": "ICE",
             "drivers": "West Africa crop weather, disease (swollen shoot), demand growth"},
            {"symbol": "CT=F",  "name": "Cotton",         "benchmark": "ICE",
             "drivers": "Apparel demand, synthetic substitution, Xinjiang policy"},
            {"symbol": "OJ=F",  "name": "Orange Juice",   "benchmark": "ICE",
             "drivers": "Florida/Brazil crop disease (citrus greening), weather"},
        ],
    },
    "Livestock & Animal Products": {
        "description": "Feed driven cost structures; biological cycles",
        "market_lens": "Feed prices, herd cycles, disease risk, trade access.",
        "items": [
            {"symbol": "LE=F",  "name": "Live Cattle",    "benchmark": "CME",
             "drivers": "Herd cycles, feed costs, beef export demand"},
            {"symbol": "GF=F",  "name": "Feeder Cattle",  "benchmark": "CME",
             "drivers": "Corn prices, pasture conditions, placement rates"},
            {"symbol": "HE=F",  "name": "Lean Hogs",      "benchmark": "CME",
             "drivers": "Pork export demand (China), disease cycles, feed costs"},
        ],
    },

    # ═══ METALS ═══
    "Ferrous Metals": {
        "description": "Construction and industrial backbone; volume driven",
        "market_lens": "Construction cycles, infrastructure spend, Chinese demand, iron ore → steel margins.",
        "items": [
            {"symbol": "PICK",  "name": "Iron Ore / Mining (ETF)", "benchmark": "iShares Metals & Mining",
             "drivers": "Chinese steel production, property sector health"},
            {"symbol": "SLX",   "name": "Steel (ETF)",    "benchmark": "VanEck Steel",
             "drivers": "Construction activity, infrastructure spend, trade tariffs"},
        ],
    },
    "Base (Industrial) Metals": {
        "description": "Cyclical, closely tied to global growth",
        "market_lens": "Industrial production, electrification intensity, inventories (LME/SHFE), cost curves.",
        "items": [
            {"symbol": "HG=F",   "name": "Copper",        "benchmark": "COMEX",
             "drivers": "Manufacturing PMI, energy transition demand, Chile/Peru supply"},
            {"symbol": "ALI=F",  "name": "Aluminium",     "benchmark": "COMEX",
             "drivers": "Energy costs (smelting), China production quotas"},
            {"symbol": "NICK.L", "name": "Nickel (ETC)",   "benchmark": "WisdomTree Nickel",
             "drivers": "EV batteries, stainless steel, Indonesia supply dominance"},
            {"symbol": "ZN=F",   "name": "Zinc",          "benchmark": "COMEX",
             "drivers": "Galvanising demand, construction cycles"},
        ],
    },
    "Precious Metals": {
        "description": "Value preservation; investment demand dominates",
        "market_lens": "Real rates, USD, investment flows, jewellery vs industrial split (notably silver, PGMs).",
        "items": [
            {"symbol": "GC=F",  "name": "Gold",           "benchmark": "COMEX",
             "drivers": "Real rates, USD, central bank buying, risk-off flows"},
            {"symbol": "SI=F",  "name": "Silver",         "benchmark": "COMEX",
             "drivers": "Gold correlation + industrial (solar PV, electronics)"},
            {"symbol": "PL=F",  "name": "Platinum",       "benchmark": "NYMEX",
             "drivers": "Auto catalyst demand, hydrogen economy, ICE vs EV transition"},
            {"symbol": "PA=F",  "name": "Palladium",      "benchmark": "NYMEX",
             "drivers": "Auto catalyst demand, Russia supply concentration, ICE vs EV transition"},
        ],
    },
    "Battery & Energy Transition Metals": {
        "description": "Policy and technology driven demand",
        "market_lens": "EV penetration, chemistry shifts (LFP vs NMC), supply concentration, permitting risk.",
        "items": [
            {"symbol": "LIT",   "name": "Lithium (ETF)",  "benchmark": "Global X Lithium",
             "drivers": "EV adoption rate, Chinese oversupply cycles, battery chemistry shifts"},
            {"symbol": "REMX",  "name": "Rare Earths (ETF)", "benchmark": "VanEck Rare Earth",
             "drivers": "China export controls, defence/tech demand, permanent magnet supply"},
        ],
    },

    # ═══ OTHER ═══
    "Industrial & Construction": {
        "description": "High tonnage construction and manufacturing inputs",
        "market_lens": "US housing starts, infrastructure spend, logistics costs, contract vs spot pricing.",
        "items": [
            {"symbol": "LBS=F", "name": "Lumber",         "benchmark": "CME",
             "drivers": "US housing starts, Canadian supply, tariffs"},
        ],
    },
}

# ─── Commodity Research Notes ───
OBSIDIAN_VAULT_PATH = Path("/Users/zalen/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZC_Mac_Vault")
COMMODITY_NOTES_DIR = OBSIDIAN_VAULT_PATH / "Commodities"

# Flat lookup: symbol → {name, category, benchmark, drivers}
COMMODITY_LOOKUP: dict[str, dict] = {
    item["symbol"]: {
        "name": item["name"],
        "category": cat,
        "benchmark": item["benchmark"],
        "drivers": item.get("drivers", ""),
    }
    for cat, sector_data in COMMODITIES.items()
    for item in sector_data["items"]
}

# ─── Commodity Forward Contracts ───
# Maps front-month =F symbol → (ticker_prefix, exchange_suffix) for Yahoo Finance
# deferred contract naming: {prefix}{month_code}{YY}.{exchange}
# ETFs (HNRG, URA, LIT, REMX, NICK.L, PICK, SLX) and TTF=F are excluded (no forward data)
COMMODITY_FORWARD_MAP: dict[str, tuple[str, str]] = {
    # Energy (NYMEX)
    "CL=F":  ("CL",  "NYM"),
    "BZ=F":  ("BZ",  "NYM"),
    "NG=F":  ("NG",  "NYM"),
    "HO=F":  ("HO",  "NYM"),
    "RB=F":  ("RB",  "NYM"),
    # Precious Metals
    "GC=F":  ("GC",  "CMX"),
    "SI=F":  ("SI",  "CMX"),
    "PL=F":  ("PL",  "NYM"),
    "PA=F":  ("PA",  "NYM"),
    # Base Metals (COMEX)
    "HG=F":  ("HG",  "CMX"),
    # Grains & Oilseeds (CBOT)
    "ZC=F":  ("ZC",  "CBT"),
    "ZW=F":  ("ZW",  "CBT"),
    "ZS=F":  ("ZS",  "CBT"),
    "ZL=F":  ("ZL",  "CBT"),
    "ZM=F":  ("ZM",  "CBT"),
    "ZO=F":  ("ZO",  "CBT"),
    "ZR=F":  ("ZR",  "CBT"),
    # Soft Commodities (ICE)
    "SB=F":  ("SB",  "ICE"),
    "KC=F":  ("KC",  "ICE"),
    "CC=F":  ("CC",  "ICE"),
    "CT=F":  ("CT",  "ICE"),
    "OJ=F":  ("OJ",  "ICE"),
    # Livestock (CME)
    "LE=F":  ("LE",  "CME"),
    "GF=F":  ("GF",  "CME"),
    "HE=F":  ("HE",  "CME"),
    # Construction (CME)
    "LBS=F": ("LBS", "CME"),
}

_FORWARD_MONTH_CODES = "FGHJKMNQUVXZ"  # Jan=F, Feb=G, Mar=H, Apr=J, May=K, Jun=M, Jul=N, Aug=Q, Sep=U, Oct=V, Nov=X, Dec=Z


def get_forward_symbol(prefix: str, exchange: str, months: int = 12) -> str:
    """Generate Yahoo Finance deferred contract symbol approximately `months` ahead."""
    from datetime import datetime
    now = datetime.now()
    total_months = now.month - 1 + months
    year = now.year + total_months // 12
    month = total_months % 12 + 1
    return f"{prefix}{_FORWARD_MONTH_CODES[month - 1]}{str(year)[-2:]}.{exchange}"

# ─── Mag 7 + AI Heavyweights ───
REFRESH_MAG7 = 120

MAG7_STOCKS = [
    {"symbol": "AAPL",  "name": "Apple",       "group": "Mag 7"},
    {"symbol": "MSFT",  "name": "Microsoft",   "group": "Mag 7"},
    {"symbol": "GOOGL", "name": "Alphabet",    "group": "Mag 7"},
    {"symbol": "AMZN",  "name": "Amazon",      "group": "Mag 7"},
    {"symbol": "NVDA",  "name": "NVIDIA",      "group": "Mag 7"},
    {"symbol": "META",  "name": "Meta",        "group": "Mag 7"},
    {"symbol": "TSLA",  "name": "Tesla",       "group": "Mag 7"},
    {"symbol": "ORCL",  "name": "Oracle",      "group": "AI Infra"},
    {"symbol": "AMD",   "name": "AMD",         "group": "AI Infra"},
    {"symbol": "TSM",   "name": "TSMC",        "group": "AI Infra"},
    {"symbol": "PLTR",  "name": "Palantir",    "group": "AI Infra"},
]

# ─── Options Skew ───
SKEW_UNDERLYING = "SPY"

# ─── Navigation ───
def all_tracked_symbols() -> list[str]:
    """Deduplicated list of every Yahoo Finance symbol tracked by the dashboard."""
    symbols: set[str] = set()

    # Indices
    for item in WORLD_INDICES:
        symbols.add(item["symbol"])

    # S&P Sectors
    for item in SP_SECTORS:
        symbols.add(item["symbol"])

    # Defense indexes
    for item in DEFENSE_INDEXES:
        symbols.add(item["symbol"])

    # Futures (nested dict of categories)
    for category_items in FUTURES.values():
        for item in category_items:
            symbols.add(item["symbol"])

    # Forex pairs
    for item in FOREX_PAIRS:
        symbols.add(item["symbol"])

    # Bonds
    for item in US_TREASURY_YIELDS:
        symbols.add(item["symbol"])
    symbols.add(MOVE_INDEX["symbol"])

    # Commodities (nested dict of sectors → {items: [...]})
    for sector_data in COMMODITIES.values():
        for item in sector_data["items"]:
            symbols.add(item["symbol"])

    # Mag 7
    for item in MAG7_STOCKS:
        symbols.add(item["symbol"])

    # Pulse indicators
    for item in PULSE_INDICATORS:
        symbols.add(item["symbol"])

    # VIX term structure
    for item in VIX_TERM_STRUCTURE:
        symbols.add(item["symbol"])

    # Rotation sectors (already in SP_SECTORS but be explicit)
    for item in ROTATION_SECTORS:
        symbols.add(item["symbol"])

    return sorted(symbols)


NAV_SECTIONS = [
    {
        "label": "Assets",
        "items": [
            {"path": "/indices", "label": "Indices", "icon": "chart-bar"},
            {"path": "/futures", "label": "Futures", "icon": "trending-up"},
            {"path": "/forex",   "label": "Forex",   "icon": "currency-dollar"},
        ],
    },
    {
        "label": "Fixed Income",
        "items": [
            {"path": "/bonds", "label": "Bonds", "icon": "building-library"},
        ],
    },
    {
        "label": "Macro",
        "items": [
            {"path": "/economy", "label": "Economy", "icon": "globe-alt"},
            {"path": "/pulse",   "label": "Macro Pulse", "icon": "bolt"},
        ],
    },
    {
        "label": "News & Events",
        "items": [
            {"path": "/news", "label": "News", "icon": "newspaper"},
        ],
    },
    {
        "label": "System",
        "items": [
            {"path": "/health", "label": "Source Health", "icon": "signal"},
        ],
    },
]
