import commonjs from '@rollup/plugin-commonjs';
import resolve from '@rollup/plugin-node-resolve';

export default {
    input: 'web/js/index.js',
    output: {
        file: 'public/js/index.js',
        format: 'iife'
    },
    plugins: [
        commonjs(),
        resolve()
    ]
};
