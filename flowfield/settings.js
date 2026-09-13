/**
 * REGENOVA FlowField Settings.
 * Runtime configuration for the Node-RED IoT Integration & Event Microservice.
 */

const path = require('path');

module.exports = {
    flowFile: 'flows.json',
    flowFilePretty: true,

    uiPort: process.env.FLOWFIELD_PORT ? parseInt(process.env.FLOWFIELD_PORT, 10) : 1880,
    uiHost: process.env.FLOWFIELD_HOST || '127.0.0.1',

    httpAdminRoot: '/',
    httpNodeRoot: '/',

    credentialSecret: process.env.FLOWFIELD_CREDENTIAL_SECRET || 'regenova-flowfield-credential-secret-key-2026',

    adminAuth: {
        type: 'credentials',
        users: [
            {
                username: 'admin',
                password: process.env.FLOWFIELD_ADMIN_HASH || '$2b$10$678EDfJxsYaWMk5hSUqvuOiHgE4yEFgVufQxc1tyc/ONppTSaG41O',
                permissions: '*'
            },
            {
                username: 'mosud',
                password: process.env.FLOWFIELD_ADMIN_HASH || '$2b$10$678EDfJxsYaWMk5hSUqvuOiHgE4yEFgVufQxc1tyc/ONppTSaG41O',
                permissions: '*'
            }
        ]
    },

    editorTheme: {
        page: {
            title: 'REGENOVA FlowField — IoT Integration',
            favicon: path.join(__dirname, 'public', 'favicon.ico')
        },
        header: {
            title: 'REGENOVA FlowField'
        },
        deployButton: {
            type: 'simple',
            caption: 'Deploy FlowField'
        },
        menu: {
            'menu-item-help': false
        }
    },

    logging: {
        console: {
            level: process.env.FLOWFIELD_LOG_LEVEL || 'info',
            metrics: false,
            audit: true
        }
    },

    contextStorage: {
        default: {
            module: 'memory'
        },
        localfs: {
            module: 'localfilesystem',
            config: {
                dir: path.join(__dirname, 'context')
            }
        }
    },

    functionGlobalContext: {
        env: process.env.NODE_ENV || 'production',
        os: require('os'),
        process: process
    },
    nodeMessageBufferLength: 2000
};
