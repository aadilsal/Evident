import { Router } from 'express';
import { z } from 'zod';
import { db } from '../db';
import { chargeCustomer } from '../lib/billing';

export const invoicesRouter = Router();

const CreateInvoice = z.object({ customerId: z.string(), amount: z.number().int().positive() });

invoicesRouter.get('/', async (_req, res) => {
  res.json(await db.invoice.findMany({ include: { customer: true } }));
});

invoicesRouter.post('/', async (req, res) => {
  const body = CreateInvoice.parse(req.body);
  const invoice = await db.invoice.create({ data: body });
  await chargeCustomer(invoice.customerId, invoice.amount);
  res.status(201).json(invoice);
});
