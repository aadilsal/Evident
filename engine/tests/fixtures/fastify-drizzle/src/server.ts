import Fastify from 'fastify';
import usersRoutes from './routes/users';

const app = Fastify();

app.register(usersRoutes, { prefix: '/users' });

app.listen({ port: 3000 });
