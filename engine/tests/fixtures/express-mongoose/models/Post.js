const { Schema, model } = require('mongoose');

const Post = model('Post', new Schema({
  title: String,
  author: { type: Schema.Types.ObjectId, ref: 'User' },
}));

module.exports = Post;
