import Fastify from "fastify";
import itemsRoutes from "./routes/items";

export async function buildApp() {
  const app = Fastify();
  app.get("/health", async () => ({ ok: true }));
  await app.register(
    async (api) => {
      api.register(itemsRoutes, { prefix: "/items" });
    },
    { prefix: "/api/v1" },
  );
  return app;
}
