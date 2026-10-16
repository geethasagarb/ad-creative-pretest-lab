import sqlite3, json, csv, bisect, datetime as dt
B='crash_backup_1131'
cfg=json.load(open('simulation_config.json'))
names={a['agent_id']:(a['entity_name'],a['entity_type']) for a in cfg['agent_configs']}
sim=cfg['simulation_id']
def round_index(path):
    starts=[]
    for line in open(path):
        e=json.loads(line)
        if e.get('event_type')=='round_start': starts.append((e['timestamp'],e['round']))
    starts.sort(); return starts
def id_rounds(path):
    m={}
    for line in open(path):
        e=json.loads(line); a=e.get('action_args') or {}
        t=e.get('action_type')
        if t=='CREATE_POST' and 'post_id' in a: m[('post',a['post_id'])]=e['round']
        if t in('QUOTE_POST','REPOST') and 'new_post_id' in a: m[('post',a['new_post_id'])]=e['round']
        if t=='CREATE_COMMENT' and 'comment_id' in a: m[('comment',a['comment_id'])]=e['round']
    return m
def ts_round(starts, ts):
    ts=ts.replace(' ','T'); i=bisect.bisect_right([s[0] for s in starts], ts)-1
    return starts[i][1] if i>=0 else 0
rows=[]
def seeds(path):
    out=set()
    for line in open(path):
        e=json.loads(line)
        if e.get('action_type')=='CREATE_POST' and e.get('round')==0: out.add(e['action_args']['content'][:120])
    return out
for plat in ['twitter','reddit']:
    c=sqlite3.connect(f'{B}/{plat}_simulation.db'); starts=round_index(f'{B}/{plat}/actions.jsonl'); idr=id_rounds(f'{B}/{plat}/actions.jsonl'); sd=seeds(f'{B}/{plat}/actions.jsonl')
    users={u:(a,h) for u,a,h in c.execute('select user_id,agent_id,name from user')}
    def rnd(v): return int(v) if isinstance(v,int) or (isinstance(v,str) and v.isdigit()) else ts_round(starts,str(v))
    for pid,uid,orig,content,quote,ca,lk,dl in c.execute('select post_id,user_id,original_post_id,content,quote_content,created_at,num_likes,num_dislikes from post'):
        a,h=users[uid]; r=0 if (not orig and (content or '')[:120] in sd) else idr.get(('post',pid), rnd(ca) if plat=='reddit' else None)
        kind='post' if not orig else ('quote' if quote else 'repost'); text=(quote if kind=='quote' else content) or ''
        rows.append(dict(reaction_id=f'{plat}_post_{pid}',simulation_id=sim,platform=plat,reaction_type=kind,
          agent_id=a,agent_name=names[a][0],agent_type=names[a][1],handle=h,round_num=r,parent_post_id=orig,content=text.replace('\r',' ').replace('\n',' '),
          num_likes=lk,num_dislikes=dl,is_seed_post=(r==0 and not orig)))
    for cid,pid,uid,content,ca,lk,dl in c.execute('select comment_id,post_id,user_id,content,created_at,num_likes,num_dislikes from comment'):
        a,h=users[uid]; r=idr.get(('comment',cid), rnd(ca))
        rows.append(dict(reaction_id=f'{plat}_comment_{cid}',simulation_id=sim,platform=plat,reaction_type='comment',
          agent_id=a,agent_name=names[a][0],agent_type=names[a][1],handle=h,round_num=r,parent_post_id=pid,content=(content or '').replace('\r',' ').replace('\n',' '),
          num_likes=lk,num_dislikes=dl,is_seed_post=False))
with open('mirofish_reactions.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
import collections
print(len(rows), collections.Counter((r['platform'],r['reaction_type']) for r in rows))
print('seed',sum(r['is_seed_post'] for r in rows),'rounds',sorted(collections.Counter(r['round_num'] for r in rows).items()))
print('types',collections.Counter(r['agent_type'] for r in rows))
print('empty content',sum(1 for r in rows if not r['content'].strip()))
