const db = require('../db');

async function listItems(req, res) {
  res.json(await db.item.findMany());
}

async function createItem(req, res) {
  res.status(201).json(await db.item.create({ data: req.body }));
}

const removeItem = async (req, res) => {
  await db.item.delete({ where: { id: req.params.id } });
  res.status(204).end();
};

module.exports = { listItems, createItem, removeItem };
