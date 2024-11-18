# Adjusting "earnings before rewards" to achieve the desired "earnings after rewards" for the specified ranges
# We will calculate the necessary "earnings_before_rewards" based on the formula for net charge:
# net_charge = earnings_before_rewards - (earnings_before_rewards * 2.5 * 0.1)

# Rearranging, we get:
# earnings_before_rewards = desired_net_charge / (1 - 2.5 * 0.1)

# Define the desired earnings after rewards for specified ranges
desired_after_rewards = {
    (20001, 35000): 70,
    (35001, 50000): 100,
    (50001, 250000): 150
}

# Define the reward conversion factors
coins_per_shilling = 2.5
cost_per_coin = 0.1
reward_multiplier = coins_per_shilling * cost_per_coin

# Calculate the necessary earnings_before_rewards for the specified ranges to meet the target after rewards
for entry in expanded_data:
    range_tuple = (entry["from_amount"], entry["to_amount"])
    
    if range_tuple in desired_after_rewards:
        target_after_rewards = desired_after_rewards[range_tuple]
        # Calculate required earnings before rewards
        required_earnings_before_rewards = target_after_rewards / (1 - reward_multiplier)
        # Calculate corresponding cost of coins
        cost_of_coins = required_earnings_before_rewards * coins_per_shilling * cost_per_coin
        
        # Update the entry with calculated values
        entry["earnings_before_rewards"] = round(required_earnings_before_rewards, 2)
        entry["cost_of_coins"] = round(cost_of_coins, 2)
        entry["earnings_after_rewards"] = target_after_rewards

print(expanded_data)
