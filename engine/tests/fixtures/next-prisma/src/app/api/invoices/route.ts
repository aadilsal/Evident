import { NextResponse } from 'next/server';
import { prisma, sendReceipt } from '@/lib';

export async function GET() {
  const invoices = await prisma.invoice.findMany();
  return NextResponse.json(invoices);
}

export const POST = async (req: Request) => {
  const body = await req.json();
  const invoice = await prisma.invoice.create({ data: body });
  await sendReceipt(body.email);
  return NextResponse.json(invoice, { status: 201 });
};
