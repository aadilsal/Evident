import type { NextFunction, Request, Response } from 'express';

export function requireAuth(req: Request, res: Response, next: NextFunction) {
  if (req.headers.authorization !== `Bearer ${process.env.API_TOKEN}`) {
    return res.status(401).end();
  }
  next();
}
