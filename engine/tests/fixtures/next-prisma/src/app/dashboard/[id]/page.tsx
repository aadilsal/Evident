import { prisma } from '@/lib/db';

export default async function InvoicePage({ params }: { params: { id: string } }) {
  const invoice = await prisma.invoice.findUnique({ where: { id: params.id } });
  return <pre>{JSON.stringify(invoice)}</pre>;
}
