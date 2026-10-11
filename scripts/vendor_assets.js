const fs = require('fs');
const path = require('path');

function vendorAssets() {
  const root = path.join(__dirname, '..');
  const vendorDir = path.join(root, 'frontend', 'vendor');
  const ortDir = path.join(vendorDir, 'ort');

  fs.mkdirSync(vendorDir, { recursive: true });
  fs.mkdirSync(ortDir, { recursive: true });

  console.log('Vendoring transformers.js and onnxruntime-web...');

  // 1. Copy transformers.js
  const transformersDist = path.join(root, 'node_modules', '@xenova', 'transformers', 'dist');
  if (fs.existsSync(transformersDist)) {
    const files = fs.readdirSync(transformersDist);
    files.forEach(file => {
      const src = path.join(transformersDist, file);
      const dst = path.join(vendorDir, file);
      if (fs.statSync(src).isFile()) {
        fs.copyFileSync(src, dst);
        console.log(`Copied ${file} to frontend/vendor/`);
      }
    });
  } else {
    console.warn('Transformers dist not found in node_modules.');
  }

  // 2. Copy onnxruntime-web
  const ortDist = path.join(root, 'node_modules', 'onnxruntime-web', 'dist');
  if (fs.existsSync(ortDist)) {
    const files = fs.readdirSync(ortDist);
    files.forEach(file => {
      if (file.endsWith('.wasm') || file.endsWith('.js')) {
        const src = path.join(ortDist, file);
        const dst = path.join(ortDir, file);
        fs.copyFileSync(src, dst);
        console.log(`Copied ${file} to frontend/vendor/ort/`);
      }
    });
  } else {
    console.warn('ONNX Runtime Web dist not found in node_modules.');
  }

  console.log('Vendoring complete!');
}

vendorAssets();
