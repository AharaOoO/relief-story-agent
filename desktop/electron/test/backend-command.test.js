const assert = require('node:assert/strict')
const test = require('node:test')

const { createBackendCommand } = require('../src/backend-command')

test('builds the development python sidecar command with AppData state', () => {
  const command = createBackendCommand({
    isDev: true,
    repoRoot: 'D:/repo',
    resourcesPath: 'D:/resources',
    userDataPath: 'C:/Users/test/AppData/Roaming/relief',
    host: '127.0.0.1',
    port: 19001,
    uiOrigin: 'http://127.0.0.1:5179',
    extraCorsOrigins: ['http://localhost:5179'],
    environment: { RUNNINGHUB_AI_API_KEY: 'secret' },
    runtimeConfig: {
      comfyui_endpoint: 'http://127.0.0.1:8199',
      max_workers: 4,
      image_generation_concurrency: 3,
      comfyui_submission_concurrency: 2,
    },
    processEnvironment: { PATH: 'system-path' },
  })

  assert.equal(command.command, 'python')
  assert.deepEqual(command.args.slice(0, 6), [
    '-m',
    'relief_story_agent.server',
    '--host',
    '127.0.0.1',
    '--port',
    '19001',
  ])
  assert.ok(
    command.args
      .map((value) => value.replaceAll('\\', '/'))
      .includes('C:/Users/test/AppData/Roaming/relief/state'),
  )
  assert.ok(command.args.includes('http://127.0.0.1:5179'))
  assert.ok(command.args.includes('http://localhost:5179'))
  assert.ok(command.args.includes('http://127.0.0.1:8199'))
  assert.deepEqual(command.args.slice(command.args.indexOf('--max-workers'), command.args.indexOf('--max-workers') + 2), ['--max-workers', '4'])
  assert.deepEqual(command.args.slice(command.args.indexOf('--image-generation-concurrency'), command.args.indexOf('--image-generation-concurrency') + 2), ['--image-generation-concurrency', '3'])
  assert.deepEqual(command.args.slice(command.args.indexOf('--comfyui-submission-concurrency'), command.args.indexOf('--comfyui-submission-concurrency') + 2), ['--comfyui-submission-concurrency', '2'])
  assert.equal(command.env.RUNNINGHUB_AI_API_KEY, 'secret')
  assert.ok(command.env.PYTHONPATH.includes('D:/repo'))
})

test('builds the packaged sidecar command from Electron resources', () => {
  const command = createBackendCommand({
    isDev: false,
    repoRoot: 'D:/repo',
    resourcesPath: 'D:/resources',
    userDataPath: 'C:/Users/test/AppData/Roaming/relief',
    host: '127.0.0.1',
    port: 19002,
    uiOrigin: 'null',
    extraCorsOrigins: [],
    environment: {},
    processEnvironment: {},
  })

  assert.match(command.command, /resources[\\/]bin[\\/]relief-story-agent-api\.exe$/)
  assert.ok(command.args.includes('19002'))
  assert.ok(command.args.includes('null'))
  assert.ok(
    command.args
      .map((value) => value.replaceAll('\\', '/'))
      .includes('C:/Users/test/AppData/Roaming/relief/state'),
  )
})
