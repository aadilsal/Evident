import express from 'express';
import { createUsersRouter } from './users.routes.js';

export function createApp() {
  const app = express();
  const v1 = express.Router();
  v1.use('/users', createUsersRouter());
  app.use('/api/v1', v1);
  return app;
}
