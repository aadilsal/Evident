import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { User } from './user.entity';

@Injectable()
export class UsersService {
  constructor(@InjectRepository(User) private readonly users: Repository<User>) {}

  findAll() {
    return this.users.find();
  }

  findOne(id: number) {
    return this.users.findOneBy({ id });
  }

  create(email: string) {
    return this.users.save({ email });
  }
}
