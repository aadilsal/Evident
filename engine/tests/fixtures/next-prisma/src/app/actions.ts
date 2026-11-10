'use server';

import { prisma } from '@/lib/db';

export async function deleteInvoice(id: string) {
  await prisma.invoice.delete({ where: { id } });
}
