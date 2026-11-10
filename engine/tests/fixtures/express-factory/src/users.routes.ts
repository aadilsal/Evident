import { Router } from 'express';
import { authenticate } from './auth.js';
import { UsersService } from './users.service.js';

export function createUsersRouter(): Router {
  const router = Router();
  const service = new UsersService();

  router.post('/', authenticate('admin'), async (req, res) => {
    res.json(await service.create(req.body));
  });

  return router;
}
