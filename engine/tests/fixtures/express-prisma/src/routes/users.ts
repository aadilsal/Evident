import { Router } from 'express';
import { db } from '../db';

export const usersRouter = Router();

usersRouter.get('/', async (_req, res) => {
  const users = await db.user.findMany({ select: { id: true, email: true } });
  res.json(users);
});

usersRouter.get('/:id', async (req, res) => {
  const user = await db.user.findUnique({ where: { id: req.params.id } });
  res.json(user);
});

// Intentionally unguarded and unvalidated: health checks should flag this.
usersRouter.post('/', async (req, res) => {
  const user = await db.user.create({ data: { email: req.body.email, name: req.body.name } });
  res.status(201).json(user);
});
