const express = require('express');
const path = require('path');

const app = express();
const PORT = Number(process.env.PORT) || 3000;
const HOST = '0.0.0.0';

app.use(express.static(__dirname, { index: 'preview.html' }));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'preview.html'));
});

app.listen(PORT, HOST, () => {
  console.log(`Profile preview server listening on http://${HOST}:${PORT}`);
});
