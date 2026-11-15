import express from 'express';
import users from './users';

const app = express();
app.use('/api', users);
app.get('*', (req, res) => {
  res.status(404).end();
});

export default app;
