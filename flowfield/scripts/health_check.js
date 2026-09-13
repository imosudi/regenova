/**
 * REGENOVA FlowField Lifecycle and Health Verification Script.
 */

const http = require('http');

const port = process.env.FLOWFIELD_PORT ? parseInt(process.env.FLOWFIELD_PORT, 10) : 1880;
const host = process.env.FLOWFIELD_HOST || '127.0.0.1';

function checkEndpoint(path) {
    return new Promise((resolve, reject) => {
        const req = http.get(`http://${host}:${port}${path}`, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                try {
                    const parsed = JSON.parse(body);
                    resolve({ statusCode: res.statusCode, data: parsed });
                } catch (e) {
                    resolve({ statusCode: res.statusCode, raw: body });
                }
            });
        });
        req.on('error', reject);
        req.setTimeout(4000, () => {
            req.destroy();
            reject(new Error(`Timeout connecting to ${path}`));
        });
    });
}

async function runChecks() {
    console.log(`[FlowField Health Check] Testing target http://${host}:${port}...`);
    try {
        const health = await checkEndpoint('/health');
        console.log(`✓ /health: Status ${health.statusCode}, payload:`, health.data);
        if (health.statusCode !== 200 || health.data.status !== 'healthy') {
            console.error('✗ /health failed validation!');
            process.exit(1);
        }

        const ready = await checkEndpoint('/ready');
        console.log(`✓ /ready: Status ${ready.statusCode}, payload:`, ready.data);
        if (ready.statusCode !== 200 || ready.data.status !== 'ready') {
            console.error('✗ /ready failed validation!');
            process.exit(1);
        }

        const info = await checkEndpoint('/api/v1/info');
        console.log(`✓ /api/v1/info: Status ${info.statusCode}, framework: ${info.data.framework}`);

        console.log('\n[SUCCESS] All FlowField health checks passed!');
        process.exit(0);
    } catch (err) {
        console.error('✗ Health check encountered connection error:', err.message);
        process.exit(1);
    }
}

runChecks();
