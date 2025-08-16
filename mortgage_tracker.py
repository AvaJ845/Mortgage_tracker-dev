def calculate_mortgage(principal, annual_rate, years):
    monthly_rate = annual_rate / 100 / 12
    number_of_payments = years * 12
    mortgage_payment = principal * (monthly_rate * (1 + monthly_rate) ** number_of_payments) / ((1 + monthly_rate) ** number_of_payments - 1)
    return mortgage_payment

# Example usage
if __name__ == '__main__':
    principal = 300000  # Example principal
    annual_rate = 3.75  # Example interest rate
    years = 30  # Example loan term
    payment = calculate_mortgage(principal, annual_rate, years)
    print(f'Monthly mortgage payment: ${payment:.2f}')