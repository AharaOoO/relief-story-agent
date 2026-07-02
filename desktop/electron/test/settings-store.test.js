const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {
  ALLOWED_SECRET_NAMES,
  SettingsStore,
} = require('../src/settings-store')

function fakeSafeStorage() {
  return {
    isEncryptionAvailable: () => true,
    encryptString: (value) => Buffer.from(`encrypted:${value}`, 'utf8'),
    decryptString: (value) => {
      const text = value.toString('utf8')
      assert.match(text, /^encrypted:/)
      return text.slice('encrypted:'.length)
    },
  }
}

async function makeStore() {
  const userDataPath = await fs.mkdtemp(path.join(os.tmpdir(), 'relief-settings-'))
  return {
    userDataPath,
    store: new SettingsStore({
      userDataPath,
      safeStorage: fakeSafeStorage(),
    }),
  }
}

test('stores runtime config separately from encrypted secrets', async () => {
  const { store, userDataPath } = await makeStore()

  await store.saveRuntimeConfig({
    comfyuiEndpoint: 'http://127.0.0.1:8188',
    workflowPath: 'D:/ComfyUI/workflows/ltx.json',
  })
  await store.saveSecret('RUNNINGHUB_AI_API_KEY', 'rh-live-secret')

  const raw = JSON.parse(
    await fs.readFile(path.join(userDataPath, 'settings.json'), 'utf8'),
  )
  assert.equal(raw.version, 1)
  assert.equal(raw.runtime.comfyuiEndpoint, 'http://127.0.0.1:8188')
  assert.notEqual(raw.secrets.RUNNINGHUB_AI_API_KEY, 'rh-live-secret')
  assert.doesNotMatch(JSON.stringify(raw), /rh-live-secret/)
  assert.deepEqual(await store.getRuntimeConfig(), {
    comfyuiEndpoint: 'http://127.0.0.1:8188',
    workflowPath: 'D:/ComfyUI/workflows/ltx.json',
  })
})

test('returns masked secret status and keeps plaintext inside main process', async () => {
  const { store } = await makeStore()
  await store.saveSecret('RUNNINGHUB_CN_API_KEY', 'cn-secret-1234')
  await store.saveSecret('RUNNINGHUB_CN_SHARED_API_KEY', 'cn-shared-5678')

  const status = await store.getSecretStatus()
  const environment = await store.getEnvironment()

  assert.equal(status.RUNNINGHUB_CN_API_KEY.configured, true)
  assert.equal(status.RUNNINGHUB_CN_API_KEY.masked, '••••1234')
  assert.equal(environment.RUNNINGHUB_CN_API_KEY, 'cn-secret-1234')
  assert.equal(status.RUNNINGHUB_CN_SHARED_API_KEY.configured, true)
  assert.equal(status.RUNNINGHUB_CN_SHARED_API_KEY.masked, '••••5678')
  assert.equal(environment.RUNNINGHUB_CN_SHARED_API_KEY, 'cn-shared-5678')
  assert.doesNotMatch(JSON.stringify(status), /cn-secret-1234/)
  assert.deepEqual(Object.keys(status).sort(), [...ALLOWED_SECRET_NAMES].sort())
})

test('rejects unknown secrets and secrets embedded in runtime config', async () => {
  const { store } = await makeStore()

  await assert.rejects(
    store.saveSecret('NOT_ALLOWED_API_KEY', 'secret'),
    /not an allowed desktop secret/,
  )
  await assert.rejects(
    store.saveRuntimeConfig({ OPENAI_API_KEY: 'must-not-be-here' }),
    /runtime config cannot contain secrets/,
  )
})

test('deletes a secret without touching runtime config', async () => {
  const { store } = await makeStore()
  await store.saveRuntimeConfig({ outputRoot: 'D:/relief-runs' })
  await store.saveSecret('OPENAI_API_KEY', 'openai-secret')

  await store.deleteSecret('OPENAI_API_KEY')

  const status = await store.getSecretStatus()
  assert.equal(status.OPENAI_API_KEY.configured, false)
  assert.deepEqual(await store.getEnvironment(), {})
  assert.deepEqual(await store.getRuntimeConfig(), {
    outputRoot: 'D:/relief-runs',
  })
})
