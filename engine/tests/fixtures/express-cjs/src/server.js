const express = require('express');
const { requireUser } = require('./auth');

const app = express();

app.use(express.json());
app.use('/v1', require('./routes'));
app.use(requireUser);
app.use('/admin', require('./routes/admin'));

module.exports = app;
