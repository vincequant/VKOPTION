#!/usr/bin/env python3
"""Test HSI pricing calculation"""

import json

# Load the portfolio data
with open('portfolio_data_enhanced.json', 'r') as f:
    data = json.load(f)

# Find HSI position
hsi_pos = None
for pos in data['positions']:
    if pos['symbol'] == 'HSI':
        hsi_pos = pos
        break

if hsi_pos:
    print("HSI Position Data:")
    print(f"  Symbol: {hsi_pos['symbol']}")
    print(f"  Position: {hsi_pos['position']} contracts")
    print(f"  Total avgCost from IB: {hsi_pos['avgCost']} HKD")
    print(f"  Calculated avg cost per contract: {hsi_pos.get('avg_cost', 0):.2f} HKD")
    print(f"  Current price: {hsi_pos.get('current_price', 0)} HKD")
    print(f"  Multiplier: {hsi_pos.get('multiplier', '50')}")
    print(f"  Market value: {hsi_pos.get('market_value', 0)} HKD")
    
    print("\nCalculations:")
    print(f"  Expected avg cost per contract: {hsi_pos['avgCost']} / {abs(hsi_pos['position'])} = {hsi_pos['avgCost'] / abs(hsi_pos['position']):.2f}")
    print(f"  Total cost basis: {abs(hsi_pos['position'])} × {hsi_pos['avgCost'] / abs(hsi_pos['position']):.2f} × {hsi_pos.get('multiplier', '50')} = {abs(hsi_pos['position']) * (hsi_pos['avgCost'] / abs(hsi_pos['position'])) * float(hsi_pos.get('multiplier', '50')):.2f} HKD")
    print(f"  Current market value: {hsi_pos['position']} × {hsi_pos.get('current_price', 0)} × {hsi_pos.get('multiplier', '50')} = {hsi_pos['position'] * hsi_pos.get('current_price', 0) * float(hsi_pos.get('multiplier', '50')):.2f} HKD")
    
    print("\nUser's expectation:")
    print(f"  User expects avg price: 169.3")
    print(f"  User's expiry value: 20 × 169.3 × 50 = {20 * 169.3 * 50:.2f} HKD")
    print(f"  Difference: Current price {hsi_pos.get('current_price', 0)} vs User's 169.3")
else:
    print("HSI position not found")