import type { Router } from 'express';
import { createRouter } from './create';

export default createRouter((router: Router) => {
  router.get('/users/:id([0-9]+)', (req, res) => {
    res.json({ id: req.params.id });
  });
  router.post('/users', (req, res) => {
    res.status(201).json(req.body);
  });
});
