const express = require('express');
const User = require('./models/User');
const Post = require('./models/Post');

const app = express();

app.get('/users', async (req, res) => {
  res.json(await User.find().lean());
});

app.post('/users', async (req, res) => {
  const user = new User(req.body);
  await user.save();
  res.status(201).json(user);
});

app.delete('/posts/:id', async (req, res) => {
  await Post.findByIdAndDelete(req.params.id);
  res.status(204).end();
});

module.exports = app;
