import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? '');

export async function chargeCustomer(customerId: string, amount: number) {
  return stripe.paymentIntents.create({ amount, currency: 'usd', metadata: { customerId } });
}
