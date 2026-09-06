// Convert a private V8 tensor capture for the independent Python replay.
import fs from 'node:fs';
import { deserialize } from 'node:v8';
const calls = deserialize(fs.readFileSync(process.argv[2]));
for (const call of calls) {
  for (const group of [call.feeds, call.outputs]) {
    for (const tensor of Object.values(group)) {
      tensor.data = Array.from(tensor.data, Number);
    }
  }
}
fs.writeFileSync(process.argv[3], JSON.stringify(calls));
