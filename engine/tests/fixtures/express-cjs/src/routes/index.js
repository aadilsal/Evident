const express = require('express');
const { listItems, createItem } = require('../controllers/items');
const asyncHandler = require('../asyncHandler');

const router = express.Router();

router.route('/items').get(listItems).post(asyncHandler(createItem));
router.get('/items/:id', asyncHandler(async (req, res) => {
  res.json({ id: req.params.id });
}));

module.exports = router;
