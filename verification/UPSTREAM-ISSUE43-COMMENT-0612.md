# Comment on oscardvs/zoteus#43 — draft, not sent

*Ticket 0612. Posted only after the pooling PR exists, with `#NN` replaced by its
number. Written against upstream `b0e0bc8`, after the maintainer's 11:28 comment
naming the pooling fix as the thing the next release waits on.*

Kept short on purpose: he described the defect himself in that thread, so
restating it would be telling him what he just said. What this adds is the
number, the reason it is a table, and the pointer.

---

The pooling fix is up: #NN, tracked as #51.

What it costs, since the thread has the defect but not a size for it. Measured on
a 257-passage, 68-query cross-lingual set (English, French, German, Vietnamese
and Russian queries against passages in the target language), with pooling as the
only variable at fp32: `granite-embedding-97m-multilingual-r2` loses 27.5% of its
MRR and 34.6% of its hit@1, `gte-multilingual-base` 12.7% and 10.3%,
`arctic-embed-m-v2` 10.3% and 14.7%. Different corpus and different task from
your German/English probe, so it is a second opinion rather than a replacement
for one.

It is a curated table rather than a setting because the value cannot be read at
load time: `1_Pooling/config.json` lives on a model's source repository, and the
`Xenova/*` and `onnx-community/*` mirrors the pipeline loads do not republish it.
So the id-inference that works for the E5 prefixes has nothing to look at, and a
setting on its own would leave anyone who does not already know the answer
exactly where they are. `ZOTEUS_EMBEDDING_POOLING` is there as the escape hatch
for a mirrored or renamed checkpoint the table cannot speak for, in the position
`ZOTEUS_EMBEDDING_PREFIXES` occupies. Every one of the 30 rows was read from the
model's own config and says which repository it came from.

@Michael-Logies — if you do run the from-source route, this is the branch worth
running it on rather than `main`: the multilingual models most affected are the
ones a German library would reach for. `multilingual-e5-small` is mean-pooled and
therefore unchanged either way, so your q8 numbers stand as measured.
