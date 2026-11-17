// Runs Vitest with an upper-case drive letter in every path.
// On Windows, when the folder is opened as "c:\..." (lower-case, as VS Code and Git Bash do),
// Vitest loads itself twice and every test fails with "Vitest failed to find the current suite"
// (or "Cannot read properties of undefined (reading 'config')").
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const upperDrive = (p) => p.replace(/^[a-z]:/, (drive) => drive.toUpperCase())
const cwd = upperDrive(process.cwd())
const vitest = upperDrive(fileURLToPath(new URL('../node_modules/vitest/vitest.mjs', import.meta.url)))
const result = spawnSync(process.execPath, [vitest, ...process.argv.slice(2)], { cwd, stdio: 'inherit' })
process.exit(result.status ?? 1)
