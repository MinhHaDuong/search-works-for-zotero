import { DatabaseSync } from 'node:sqlite';
const STOP=new Set(['the','a','an','and','or','of','to','in','on','for','with','is','are','was','were','be','by','as','at','that','this','it','from','we','our','their','its','these','those']);
const tok=t=>(t.toLowerCase().match(/[a-z0-9]+/g)??[]).filter(x=>x.length>1&&!STOP.has(x));
const d=new DatabaseSync('file:/home/haduong/.zoteus-bench-0003/search-index.sqlite?mode=ro',{readOnly:true});
const OUT='DH8EXSVA';
const sel=d.prepare(`SELECT m.item item, m.id id, passages.body body FROM passages
  JOIN passage_meta m ON m.rowid=passages.rowid WHERE passages MATCH ?`);
// corpus stats
const N=d.prepare('SELECT count(*) n FROM passage_meta').get().n;
const Nx=d.prepare("SELECT count(*) n FROM passage_meta WHERE item<>?").get(OUT).n;
const avg=d.prepare('SELECT avg(length(body)) a FROM passages').get().a/5.5;      // rough tokens
const avgx=d.prepare('SELECT avg(length(passages.body)) a FROM passages JOIN passage_meta m ON m.rowid=passages.rowid WHERE m.item<>?').get(OUT).a/5.5;
const dfq=d.prepare('SELECT count(*) n FROM passages WHERE passages MATCH ?');
const dfqx=d.prepare('SELECT count(*) n FROM passages JOIN passage_meta m ON m.rowid=passages.rowid WHERE passages MATCH ? AND m.item<>?');
const k1=1.5,b=0.75;
function rank(terms,{excl}){
  const N_=excl?Nx:N, avg_=excl?avgx:avg;
  const df={}; for(const t of terms) df[t]=(excl?dfqx.get('"'+t+'"',OUT):dfq.get('"'+t+'"')).n;
  const rows=sel.all(terms.map(t=>'"'+t+'"').join(' OR ')).filter(r=>!excl||r.item!==OUT);
  const hits=rows.map(r=>{
    const ts=tok(r.body), len=ts.length, tf={};
    for(const t of ts) tf[t]=(tf[t]??0)+1;
    let s=0;
    for(const t of terms){ const f=tf[t]; if(!f) continue;
      const n=df[t]??0, idf=Math.log(1+(N_-n+0.5)/(n+0.5));
      s+=idf*((f*(k1+1))/(f+k1*(1-b+b*len/avg_))); }
    return {item:r.item,s};
  }).filter(h=>h.s>0).sort((a,b)=>b.s-a.s);
  const seen=new Set(), out=[];
  for(const h of hits){ if(seen.has(h.item))continue; seen.add(h.item); out.push(h.item); if(out.length>=10)break; }
  return out;
}
for(const q of ['walras general equilibrium','keynes uncertainty expectations','carbon tax revenue recycling','cournot duopoly competition']){
  const terms=tok(q);
  const a=rank(terms,{excl:false}), bb=rank(terms,{excl:true});
  const inter=a.filter(x=>bb.includes(x)).length;
  const same=a.filter((x,i)=>bb[i]===x).length;
  console.log(`\n"${q}"`);
  console.log('  with dict   :', a.slice(0,5).join(' '));
  console.log('  without     :', bb.slice(0,5).join(' '));
  console.log(`  top-10 overlap ${inter}/10   same position ${same}/10   top-1 ${a[0]===bb[0]?'SAME':'CHANGED'}`);
}
