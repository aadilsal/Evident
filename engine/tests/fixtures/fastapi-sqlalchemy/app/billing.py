import stripe


def charge(amount: int):
    return stripe.PaymentIntent.create(amount=amount, currency="usd")
