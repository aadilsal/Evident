const { Router } = require('express');
const items = require('../controllers/items');

const router = Router();

router.delete('/items/:id', items.removeItem);

module.exports = router;
