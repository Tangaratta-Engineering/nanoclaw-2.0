// Postgres access without a driver: runs psql inside the hp-db container over its local socket (role "claims").
// Values travel as ONE json document in a psql variable and are used as (:'j')::jsonb, so psql quotes them:
// nothing from an email or invoice is ever spliced into SQL text.
import { execFile } from 'node:child_process';
import fs from 'node:fs';

export function makeDb({ container = 'hp-db', database = process.env.CLAIMS_DB || 'claims', run = execFile } = {}) {
  /** Run `sql` with `params` available as (:'j')::jsonb. Returns the parsed JSON of the last column of the last row. */
  function q(sql, params = {}) {
    return new Promise((resolve, reject) => {
      const args = ['exec', '-i', container, 'psql', '-U', 'claims', '-d', database, '-X', '-q', '-At', '-v', 'ON_ERROR_STOP=1', '-v', `j=${JSON.stringify(params)}`];
      const p = run('docker', args, { timeout: 20000, maxBuffer: 4 * 1024 * 1024 }, (err, stdout, stderr) => {
        if (err) return reject(new Error('database error: ' + String(stderr || err.message).split('\n')[0].slice(0, 200)));
        const lines = String(stdout).trim().split('\n').filter(Boolean);
        const last = lines[lines.length - 1];
        if (!last) return resolve(null);
        try { resolve(JSON.parse(last)); } catch { resolve(last); }
      });
      p.stdin.end(sql);
    });
  }
  async function migrate(schemaFile) {
    await q(fs.readFileSync(schemaFile, 'utf8'));
  }
  return { q, migrate };
}
