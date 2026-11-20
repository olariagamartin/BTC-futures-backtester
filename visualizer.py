import os
import matplotlib
matplotlib.use('Agg') # Headless backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/results"

def plot_backtest_results(result: dict, save_filename: str = None) -> str:
    """
    Generates a multi-panel chart:
    - Panel 1: BTC Price with Long/Short Trade Entry & Exit Markers
    - Panel 2: Strategy Equity Curve vs BTC Buy & Hold Benchmark
    - Panel 3: Drawdown Chart
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    strategy_name = result['strategy_name']
    leverage = result['leverage']
    metrics = result['metrics']
    eq_df = result['equity_curve']
    trades_df = result['trades']

    if save_filename is None:
        save_filename = f"backtest_{strategy_name}_{int(leverage)}x.png"
    out_path = os.path.join(RESULTS_DIR, save_filename)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1.5, 1]})
    fig.patch.set_facecolor('#131722') # Dark tradingview style

    # Style common to all axes
    for ax in (ax1, ax2, ax3):
        ax.set_facecolor('#1e222d')
        ax.grid(True, color='#2a2e39', linestyle='--', linewidth=0.5)
        ax.tick_params(colors='#d1d4dc')
        for spine in ax.spines.values():
            spine.set_color('#2a2e39')

    # --- PANEL 1: BTC Price & Trades ---
    ax1.plot(eq_df['timestamp'], eq_df['close'], color='#2962ff', label='BTC/USDT Futures Price', linewidth=1.2)
    
    # Overlay trade points
    if not trades_df.empty:
        long_entries = trades_df[trades_df['type'] == 'LONG']
        short_entries = trades_df[trades_df['type'] == 'SHORT']
        
        ax1.scatter(long_entries['entry_time'], long_entries['entry_price'], 
                    color='#00e676', marker='^', s=60, label='Long Entry', zorder=5)
        ax1.scatter(short_entries['entry_time'], short_entries['entry_price'], 
                    color='#ff5252', marker='v', s=60, label='Short Entry', zorder=5)

    ax1.set_ylabel('BTC Price (USDT)', color='#d1d4dc', fontsize=11)
    ax1.set_title(
        f"Strategy: {strategy_name} | Leverage: {leverage}x | Return: {metrics['total_return_pct']:.1f}% | "
        f"Sharpe: {metrics['sharpe_ratio']:.2f} | Max DD: {metrics['max_drawdown_pct']:.1f}% | "
        f"Liquidations: {metrics['liquidations']}",
        color='#f0f3fa', fontsize=13, fontweight='bold', pad=12
    )
    ax1.legend(loc='upper left', facecolor='#1e222d', edgecolor='#2a2e39', labelcolor='#d1d4dc')

    # --- PANEL 2: Equity Curve vs Buy & Hold ---
    initial_balance = metrics['initial_balance']
    btc_norm = (eq_df['close'] / eq_df['close'].iloc[0]) * initial_balance
    
    ax2.plot(eq_df['timestamp'], eq_df['equity'], color='#00e676', label=f'Strategy Equity ({leverage}x)', linewidth=1.6)
    ax2.plot(eq_df['timestamp'], btc_norm, color='#f2a900', linestyle='--', label='BTC Buy & Hold Benchmark', linewidth=1.2)
    ax2.axhline(initial_balance, color='#787b86', linestyle=':', linewidth=0.8)
    ax2.set_ylabel('Portfolio Equity (USDT)', color='#d1d4dc', fontsize=11)
    ax2.legend(loc='upper left', facecolor='#1e222d', edgecolor='#2a2e39', labelcolor='#d1d4dc')

    # --- PANEL 3: Drawdown ---
    peak = eq_df['equity'].cummax()
    drawdown = (eq_df['equity'] - peak) / peak * 100
    ax3.fill_between(eq_df['timestamp'], drawdown, 0, color='#ff5252', alpha=0.4, label='Drawdown %')
    ax3.set_ylabel('Drawdown (%)', color='#d1d4dc', fontsize=11)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax3.legend(loc='lower left', facecolor='#1e222d', edgecolor='#2a2e39', labelcolor='#d1d4dc')

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

    print(f"Chart saved to {out_path}")
    return out_path
