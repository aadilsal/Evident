import { DataSource } from 'typeorm';
import { Post } from './users/post.entity';

const AppDataSource = new DataSource({ type: 'postgres' });

export async function seed() {
  await AppDataSource.getRepository(Post).save({ title: 'Hello' });
}
