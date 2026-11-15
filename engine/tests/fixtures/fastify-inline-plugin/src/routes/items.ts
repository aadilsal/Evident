import { FastifyInstance } from "fastify";

export default async function (fastify: FastifyInstance) {
  fastify.get("/", async () => []);
  fastify.get("/:id", async () => ({}));
}
