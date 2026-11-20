import os
import pandas as pd
from data_loader import load_data
from strategies import EMACrossoverStrategy, RSIBollingerStrategy, ATRBreakoutStrategy
from backtester import PerpetualFuturesBacktester
from visualizer import plot_backtest_results

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/results"

def run_all_comparisons():
    print("=" * 80)
    print("   BTC PERPETUAL FUTURES STRATEGY BENCHMARK & BACKTEST")
    print("=" * 80)

    # 1. Load data
    try:
        df = load_data("btc_futures_1h.csv")
    except FileNotFoundError:
        print("Data file not found. Fetching real data first...")
        from data_loader import fetch_and_save_ohlcv
        df = fetch_and_save_ohlcv(days=322)

    start_date = df['timestamp'].iloc[0].strftime('%Y-%m-%d')
    end_date = df['timestamp'].iloc[-1].strftime('%Y-%m-%d')
    btc_start = df['close'].iloc[0]
    btc_end = df['close'].iloc[-1]
    btc_return = ((btc_end - btc_start) / btc_start) * 100.0

    print(f"Data period: {start_date} to {end_date} ({len(df)} 1-hour candles)")
    print(f"BTC Start Price: ${btc_start:,.2f} | End Price: ${btc_end:,.2f} | Buy & Hold: {btc_return:+.2f}%\n")

    # 2. Strategies to benchmark
    strategies = [
        EMACrossoverStrategy(fast_period=9, slow_period=21, trend_filter_period=168, sl_pct=0.03, tp_pct=0.03),
        RSIBollingerStrategy(bb_period=20, bb_std=2.0, rsi_period=14, rsi_oversold=30, rsi_overbought=70, sl_pct=0.025, tp_pct=0.05),
        ATRBreakoutStrategy(channel_period=24, atr_period=14, atr_multiplier=2.5, tp_pct=0.08)
    ]

    leverage_levels = [2.0, 5.0, 10.0]
    summary_rows = []

    for strat in strategies:
        print(f"\n---> Evaluating Strategy: {strat.name}")
        for lev in leverage_levels:
            engine = PerpetualFuturesBacktester(
                initial_balance=10000.0,
                leverage=lev,
                position_alloc_pct=0.90,  # 90% allocation
                taker_fee=0.0002,         # 0.05% taker fee
                slippage=0.0003,          # 0.03% slippage
                funding_rate_8h=0.0001    # 0.01% / 8hr
            )
            res = engine.run(df, strat)
            m = res['metrics']

            # Save chart for 5x leverage
            if lev == 5.0:
                chart_path = plot_backtest_results(res)
                # Export trades to CSV
                trades_csv = os.path.join(RESULTS_DIR, f"trades_{strat.name}_{int(lev)}x.csv")
                res['trades'].to_csv(trades_csv, index=False)

            summary_rows.append({
                'Strategy': strat.name,
                'Leverage': f"{int(lev)}x",
                'Return (%)': f"{m['total_return_pct']:+.1f}%",
                'Final Equity ($)': f"${m['final_equity']:,.2f}",
                'Max DD (%)': f"{m['max_drawdown_pct']:.1f}%",
                'Sharpe': f"{m['sharpe_ratio']:.2f}",
                'Win Rate (%)': f"{m['win_rate_pct']:.1f}%",
                'Profit Factor': f"{m['profit_factor']:.2f}" if m['profit_factor'] < 100 else "N/A",
                'Total Trades': m['total_trades'],
                'Liquidations': m['liquidations'],
                'Total Fees ($)': f"${m['total_fees_paid']:,.2f}"
            })

    # 3. Print Results Table
    summary_df = pd.DataFrame(summary_rows)
    print("\n" + "=" * 105)
    print("                                      FINAL STRATEGY COMPARISON")
    print("=" * 105)
    print(summary_df.to_string(index=False))
    print("=" * 105)

    summary_df.to_csv(os.path.join(RESULTS_DIR, "strategy_comparison_summary.csv"), index=False)
    print(f"\nDetailed CSV comparison saved to {os.path.join(RESULTS_DIR, 'strategy_comparison_summary.csv')}")

if __name__ == "__main__":
    run_all_comparisons()
