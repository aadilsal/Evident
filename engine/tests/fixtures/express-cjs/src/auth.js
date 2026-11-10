function requireUser(req, res, next) {
  if (!req.session?.userId) return res.status(401).end();
  return next();
}

module.exports = { requireUser };
