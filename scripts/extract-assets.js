#!/usr/bin/env node
const fs = require('fs')
const { basename, join } = require('path')

const SOURCE_ASSETS_DIR = process.argv.slice(2).shift()

if (!SOURCE_ASSETS_DIR || !fs.existsSync(SOURCE_ASSETS_DIR)) {
  console.error(`Usage: ${basename(__filename)} <source assets directory>`)
  process.exit(1)
}

const names = fs.readdirSync(SOURCE_ASSETS_DIR, { encoding: 'utf-8' })

if (!fs.existsSync(join(SOURCE_ASSETS_DIR, 'assets'))) {
  fs.mkdirSync(join(SOURCE_ASSETS_DIR, 'assets'))
}

for (const name of names) {
    const sub = join(SOURCE_ASSETS_DIR, name)
    const files = fs.readdirSync(sub, { encoding: 'utf-8', recursive: true })
    const data = files.find((file) => file.endsWith('_data'))
    if (data) {
        fs.cpSync(join(sub, data), join(SOURCE_ASSETS_DIR, 'assets', name))
    }
}
