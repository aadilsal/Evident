import express from 'express';
import { prisma } from '@acme/db';

const app = express();

app.post('/orders', async (req, res) => {
  res.json(await prisma.order.create({ data: { total: 1, items: { create: [{ sku: 'a' }] } } }));
});

app.listen(4000);
