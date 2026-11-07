import express from 'express';
import { requireAuth } from './middleware/auth';
import { invoicesRouter } from './routes/invoices';
import { usersRouter } from './routes/users';

export const app = express();
app.use(express.json());

app.get('/health', (_req, res) => res.json({ ok: true }));
app.use('/api/users', usersRouter);
app.use('/api/invoices', requireAuth, invoicesRouter);
