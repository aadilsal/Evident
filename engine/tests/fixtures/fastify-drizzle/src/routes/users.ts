import type { FastifyInstance, FastifyRequest } from 'fastify';
import { eq } from 'drizzle-orm';
import { db } from '../db';
import { users } from '../db/schema';

async function updateUser(req: FastifyRequest<{ Params: { id: string } }>) {
  return db.update(users).set(req.body as object).where(eq(users.id, Number(req.params.id)));
}

export default async function usersRoutes(fastify: FastifyInstance) {
  fastify.get('/', async () => db.select().from(users));

  fastify.post('/', { preHandler: [fastify.authenticate] }, async (req) => {
    return db.insert(users).values(req.body as { email: string });
  });

  fastify.route({ method: ['PUT'], url: '/:id', handler: updateUser });

  fastify.get('/:id/posts', async () => db.query.posts.findMany());
}
