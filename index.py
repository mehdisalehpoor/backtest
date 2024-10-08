import json
import requests
import pandas as pd
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk
import ta
from getListDate import get_first_trading_date

# Load the JSON file
with open('signals.json') as f:
    signals = json.load(f)

# Extract dates and symbols
signal_data = []
for signal_group in signals:
    for signal in signal_group:
        signal_data.append({'Date': datetime.strptime(signal['Date'], '%Y-%m-%dT%H:%M:%S.%fZ'), 'Symbol': signal['Symbol']})

# Sort signals by symbol and date
signal_data = sorted(signal_data, key=lambda x: (x['Symbol'], x['Date']))

# Function to fetch historical data for a symbol over a date range
def fetch_historical_data(symbol, start_date, end_date):
    # print(start_date)
    base_url = "https://api.binance.com/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': '1d',
        'startTime': int(start_date.timestamp() * 1000),
        'endTime': int(end_date.timestamp() * 1000),
        'limit': 1000  # Maximum limit to get as much data as possible
    }
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if response.status_code != 200 or not data:
        print(f"Error fetching data for {symbol} from {start_date} to {end_date}: {data}")
        return pd.DataFrame()  # Return empty DataFrame on error
    
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                      'close_time', 'quote_asset_volume', 'number_of_trades', 
                                      'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 
                                      'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    return df

# Pre-fetch historical data for each symbol
historical_data_dict = {}
today = datetime.now()
i=0
for signal in signal_data:
    symbol = signal['Symbol']
    if symbol not in historical_data_dict:
        symbol_data = pd.DataFrame()
        # Loop through every year from start_date to today
        if(i==0):
            # Get the earliest start date from the signals
            symbol_list_date = get_first_trading_date(symbol)
            current_start = symbol_list_date
        else:
            current_start = signal['Date']
        while current_start < today:
            current_end = min(current_start + timedelta(days=365), today)  # Get the end date for one year
            yearly_data = fetch_historical_data(symbol, current_start, current_end)
            symbol_data = pd.concat([symbol_data, yearly_data], ignore_index=True)  # Concatenate yearly data
            current_start = current_end  # Move to the next year
        
        historical_data_dict[symbol] = symbol_data
i=i+1
# Continue with your calculations (e.g., calculate RSI, etc.)
# Calculate RSI
def calculate_rsi(data, period=14):
    rsi = ta.momentum.RSIIndicator(data['close'], window=period).rsi()
    return rsi

# Calculate maximum upward and downward percentage and find 20% increase
def calculate_max_upward_downward_and_20percent(data, signal_close, signal_date):
    max_upward = ((data['high'].max() - signal_close) / signal_close) * 100
    max_downward = ((data['low'].min() - signal_close) / signal_close) * 100
    result_20percent = ''
    rows = data.head(30)  # Get the first 10 rows

    for i, row in rows.iterrows():
        days = (row['timestamp'] - signal_date).days
        if ((row['high'] - signal_close) / signal_close) * 100 >= 5:
            result_20percent = f"20 ({days} days)"
            break

    # If no 5% profit is found within the first 10 days, check the last row's close
    if not result_20percent:
        last_close = rows.iloc[-1]['close']
        percent_change = ((last_close - signal_close) / signal_close) * 100
        result_20percent = f"{percent_change:.2f}%"
        days_to_20percent = (rows.iloc[-1]['timestamp'] - signal_date).days
    else:
        days_to_20percent = days
    
    return max_upward, max_downward, result_20percent, days_to_20percent

results = []
wallet = 100  # Initial wallet amount

for index, signal in enumerate(signal_data):
    symbol = signal['Symbol']
    signal_date = signal['Date']

    historical_data = historical_data_dict[symbol]

    # Extract the data from 30 days before the signal date to today
    relevant_data = historical_data[(historical_data['timestamp'] >= signal_date - timedelta(days=30)) & (historical_data['timestamp'] <= today)]
    relevant_data_rsi = historical_data[(historical_data['timestamp'] >= signal_date - timedelta(days=index)) & (historical_data['timestamp'] <= today)]
    
    if len(relevant_data) > 31:
        signal_open = relevant_data.iloc[31]['open']
        rsi = calculate_rsi(relevant_data_rsi).iloc[index]
        # print(rsi,signal_date)
        if rsi >= 70:
            max_upward, max_downward, result_20percent, days_to_20percent = calculate_max_upward_downward_and_20percent(relevant_data.iloc[31:], signal_open, signal_date)
            results_length = len(results)

            if results_length > 0:  # Check if results have data
                last_result = results[-1]
                last_date = datetime.strptime(last_result['Date'], '%Y-%m-%dT%H:%M:%S.%fZ')
                last_days = last_result['Days']
                new_date = last_date + timedelta(days=last_days)

                # Compare new_date to signal_date only when results have data
                if new_date <= signal_date:
                    # Update wallet based on 20% Increase column
                    if '20 (' in result_20percent:
                        wallet_change = 5
                    else:
                        wallet_change = float(result_20percent.replace('%', ''))

                    wallet += wallet * wallet_change / 100

                    results.append({
                        'Date': signal_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                        'Symbol': symbol,
                        # 'Max Upward (%)': max_upward,
                        'Max Downward (%)': max_downward,
                        '20% Increase': result_20percent,
                        'Days': days_to_20percent,
                        'Wallet': wallet
                    })
            else:
                # Update wallet based on 20% Increase column
                if '20 (' in result_20percent:
                    wallet_change = 5
                else:
                    wallet_change = float(result_20percent.replace('%', ''))
                results.append({
                    'Date': signal_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                    'Symbol': symbol,
                    # 'Max Upward (%)': max_upward,
                    'Max Downward (%)': max_downward,
                    '20% Increase': result_20percent,
                    'Days': days_to_20percent,
                    'Wallet': wallet
                })

# Check if results are empty before proceeding
if results:
    # Convert results to DataFrame and sort by date
    results_df = pd.DataFrame(results)
    results_df['Date'] = pd.to_datetime(results_df['Date'])  # Ensure 'Date' is a datetime type
    results_df = results_df.sort_values(by='Date')

    # Assign Signal Number based on sorted date
    results_df['Signal Number'] = range(1, len(results_df) + 1)

    # Create GUI with tkinter
    class SignalAnalysisApp:
        def __init__(self, root, dataframe):
            self.root = root
            self.root.title("Signal Analysis")
            
            # Set the window to fullscreen or adjust to screen size
            # self.root.attributes('-fullscreen', True)  # Uncomment for fullscreen
            # Uncomment the next line for a fixed size based on screen dimensions
            self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")  

            frame = ttk.Frame(root, padding="10")
            frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)

            # Create Treeview
            self.tree = ttk.Treeview(frame, columns=list(dataframe.columns), show='headings', height=20)
            self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

            # Define headings
            for col in dataframe.columns:
                self.tree.heading(col, text=col)
                self.tree.column(col, anchor=tk.CENTER, width=210)

            # Insert data into Treeview
            for index, row in dataframe.iterrows():
                self.tree.insert("", "end", values=list(row))

            # Add vertical scrollbar
            vscrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
            vscrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            self.tree.configure(yscrollcommand=vscrollbar.set)

            # Add horizontal scrollbar
            hscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
            hscrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
            self.tree.configure(xscrollcommand=hscrollbar.set)

    # Initialize the GUI
    root = tk.Tk()
    app = SignalAnalysisApp(root, results_df)
    root.mainloop()
else:
    print("No results to display.")
