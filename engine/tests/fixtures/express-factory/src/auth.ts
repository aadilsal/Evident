export function authenticate(role: string) {
  return (req: { user?: { role: string } }, _res: unknown, next: () => void) => {
    if (req.user?.role !== role) throw new Error('forbidden');
    next();
  };
}
