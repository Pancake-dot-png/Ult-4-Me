const { app } = require('electron');
app.whenReady().then(() => {
  try {
    console.log('loading opencv-wasm...');
    const { cv } = require('opencv-wasm');
    console.log('loaded OK, Mat:', typeof cv.Mat);
    console.log('matchTemplate:', typeof cv.matchTemplate);
    const m = new cv.Mat(10, 10, cv.CV_8UC3);
    console.log('Mat created:', m.rows, 'x', m.cols);
    m.delete();
    console.log('ALL GOOD');
  } catch(e) {
    console.error('FAILED:', e.message);
    console.error(e.stack);
  }
  app.quit();
});
