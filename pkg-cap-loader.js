// pkg-cap-loader.js - 动态加载 cap 模块的包装器
let cap = null;

try {
    // 首先尝试从正常路径加载
    cap = require('cap');
} catch (err) {
    console.warn('Warning: Failed to load cap module from normal path:', err.message);
    
    try {
        // 尝试从原生模块路径加载
        const path = require('path');
        const capPath = path.join(__dirname, 'node_modules', 'cap', 'build', 'Release', 'cap.node');
        cap = require(capPath);
    } catch (err2) {
        console.error('Error: Failed to load cap module:', err2.message);
        console.error('Please install cap module properly or run with Node.js instead of pkg');
        process.exit(1);
    }
}

module.exports = cap;
