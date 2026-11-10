import { prisma } from './db.js';

export class UsersService {
  async create(data: { email: string }) {
    return prisma.user.create({ data });
  }
}
