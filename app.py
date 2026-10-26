import os, io, sqlite3, secrets
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import qrcode
load_dotenv()
ROOT=os.path.dirname(os.path.abspath(__file__)); DB=os.path.join(ROOT,'bar_tapas.db')
USER=os.getenv('ADMIN_USER','admin'); PASSWORD=os.getenv('ADMIN_PASSWORD','cambia-esta-contrasena'); BASE=os.getenv('BASE_URL','http://127.0.0.1:8000').rstrip('/')
app=FastAPI(title='Bar de Tapas QR'); auth=HTTPBasic()
def db():
 c=sqlite3.connect(DB,timeout=10); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS tables(id INTEGER PRIMARY KEY,name TEXT UNIQUE,active INTEGER DEFAULT 1); CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT,category TEXT,description TEXT DEFAULT '',price_cents INTEGER,available INTEGER DEFAULT 1); CREATE TABLE IF NOT EXISTS visits(id INTEGER PRIMARY KEY,table_id INTEGER,status TEXT DEFAULT 'open',code TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,visit_id INTEGER,table_id INTEGER,status TEXT,notes TEXT,total_cents INTEGER,paid INTEGER DEFAULT 0,created_at TEXT); CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,order_id INTEGER,product_id INTEGER,product_name TEXT,quantity INTEGER,unit_price_cents INTEGER,notes TEXT DEFAULT '');''')
  if not c.execute('SELECT COUNT(*) FROM tables').fetchone()[0]: c.executemany('INSERT INTO tables(name) VALUES(?)',[(f'Mesa {i}',) for i in range(1,11)])
  if not c.execute('SELECT COUNT(*) FROM products').fetchone()[0]: c.executemany('INSERT INTO products(name,category,description,price_cents) VALUES(?,?,?,?)',[('Patatas bravas','Tapas','',650),('Croquetas caseras','Tapas','',850),('Tortilla española','Tapas','',450),('Calamares','Raciones','',1100),('Aceitunas','Para picar','',250),('Caña','Bebidas','',250),('Agua','Bebidas','',180)])
init()
def admin(cr:HTTPBasicCredentials=Depends(auth)):
 if not secrets.compare_digest(cr.username,USER) or not secrets.compare_digest(cr.password,PASSWORD): raise HTTPException(401,'Acceso restringido',headers={'WWW-Authenticate':'Basic'})
 return cr.username
def money(n): return f'{n/100:.2f} €'.replace('.',',')
CSS="<meta name='viewport' content='width=device-width,initial-scale=1'><style>body{font:16px system-ui;margin:0;background:#f4f6f8;color:#17202a}header,.card{background:white;padding:16px;border:1px solid #ddd;border-radius:12px;margin:12px}header a{margin-right:12px;color:#126e5b}main{max-width:1000px;margin:20px auto;padding:0 12px}.item{display:flex;justify-content:space-between;border-bottom:1px solid #eee;padding:10px}button{background:#126e5b;color:white;border:0;border-radius:8px;padding:10px;cursor:pointer}input,textarea,select{padding:9px;margin:4px;border:1px solid #bbb;border-radius:7px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}</style>"
def page(title,body,script=''): return HTMLResponse("<!doctype html><html lang='es'><head><meta charset='utf-8'><title>"+title+"</title>"+CSS+"</head><body><header><b>🍴 Bar de Tapas QR</b><p><a href='/'>Carta</a><a href='/caja'>Caja</a><a href='/cocina'>Cocina</a><a href='/admin'>Administración</a></p></header><main>"+body+"</main>"+script+"</body></html>")
class It(BaseModel): product_id:int; quantity:int=Field(ge=1,le=30); notes:str=''
class Order(BaseModel): table_id:int; items:list[It]; notes:str=''; access_code:str=''
@app.get('/')
def root(): return RedirectResponse('/mesa/1')
@app.get('/mesa/{tid}')
def menu(tid:int):
 with db() as c:
  t=c.execute('SELECT * FROM tables WHERE id=? AND active=1',(tid,)).fetchone(); ps=c.execute('SELECT * FROM products WHERE available=1 ORDER BY category,name').fetchall()
 if not t: raise HTTPException(404,'Mesa no disponible')
 body=f'<h1>Carta · {t["name"]}</h1><p>Selecciona las tapas y envía el pedido. Pagarás en caja o al camarero.</p>'; groups={}
 for p in ps: groups.setdefault(p['category'],[]).append(p)
 for cat,arr in groups.items():
  body+=f'<section class="card"><h2>{cat}</h2>'
  for p in arr: body+=f'<div class="item"><div><b>{p["name"]}</b><p>{p["description"]}</p><b>{money(p["price_cents"])}</b></div><span><button onclick="chg({p["id"]},-1)">−</button> <b id="q{p["id"]}">0</b> <button onclick="chg({p["id"]},1)">+</button></span></div>'
  body+='</section>'
 body+='<section class="card"><h2>Tu pedido</h2><textarea id="notes" placeholder="Observaciones"></textarea><p>Total: <b id="total">0,00 €</b></p><button onclick="send()">Enviar pedido</button><p id="msg"></p></section>'
 script="<script>const tid="+str(tid)+",ps="+str([[p['id'],p['price_cents']] for p in ps]).replace("'",'"')+";let cart={};function chg(id,d){cart[id]=Math.max(0,(cart[id]||0)+d);document.getElementById('q'+id).textContent=cart[id];let n=0;ps.forEach(p=>n+=(cart[p[0]]||0)*p[1]);document.getElementById('total').textContent=(n/100).toLocaleString('es-ES',{style:'currency',currency:'EUR'})}async function send(){let items=ps.filter(p=>cart[p[0]]>0).map(p=>({product_id:p[0],quantity:cart[p[0]]}));if(!items.length)return alert('Añade productos');let r=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({table_id:tid,items,notes:document.getElementById('notes').value})});let j=await r.json();document.getElementById('msg').textContent=r.ok?'Pedido #'+j.id+' enviado. Código de cuenta: '+j.code:(j.detail||'Error');}</script>"
 return page('Carta',body,script)
@app.post('/api/orders')
def new_order(o:Order):
 if not o.items: raise HTTPException(400,'Pedido vacío')
 with db() as c:
  if not c.execute('SELECT id FROM tables WHERE id=? AND active=1',(o.table_id,)).fetchone(): raise HTTPException(400,'Mesa inválida')
  v=c.execute("SELECT * FROM visits WHERE table_id=? AND status='open' ORDER BY id DESC LIMIT 1",(o.table_id,)).fetchone()
  if v and o.access_code and not secrets.compare_digest(v['code'],o.access_code): raise HTTPException(403,'Código incorrecto')
  if not v:
   code=f'{secrets.randbelow(10000):04d}'; vid=c.execute("INSERT INTO visits(table_id,status,code,created_at) VALUES(?,'open',?,?)",(o.table_id,code,now())).lastrowid
  else: vid=v['id']; code=v['code']
  total=0; resolved=[]
  for i in o.items:
   p=c.execute('SELECT * FROM products WHERE id=? AND available=1',(i.product_id,)).fetchone()
   if not p: raise HTTPException(400,'Producto no disponible')
   total+=p['price_cents']*i.quantity; resolved.append((p,i))
  oid=c.execute("INSERT INTO orders(visit_id,table_id,status,notes,total_cents,created_at) VALUES(?,?,'nuevo',?,?,?)",(vid,o.table_id,o.notes,total,now())).lastrowid
  for p,i in resolved: c.execute('INSERT INTO items(order_id,product_id,product_name,quantity,unit_price_cents,notes) VALUES(?,?,?,?,?,?)',(oid,p['id'],p['name'],i.quantity,p['price_cents'],i.notes))
 return {'id':oid,'total_cents':total,'code':code,'visit_id':vid}
def orders(active=True):
 with db() as c:
  q='SELECT o.*,t.name table_name,v.code FROM orders o JOIN tables t ON t.id=o.table_id JOIN visits v ON v.id=o.visit_id'
  if active:q+=" WHERE o.status!='servido'"
  q+=' ORDER BY o.id DESC'; out=[]
  for o in c.execute(q).fetchall():
   d=dict(o); d['items']=[dict(x) for x in c.execute('SELECT * FROM items WHERE order_id=?',(o['id'],)).fetchall()]; out.append(d)
  return out
@app.get('/api/orders')
def api_orders(active:bool=True,u=Depends(admin)): return orders(active)
@app.patch('/api/orders/{oid}')
def update(oid:int,b:dict,u=Depends(admin)):
 state=b.get('status','nuevo')
 if state not in {'nuevo','aceptado','preparacion','listo','servido'}: raise HTTPException(400,'Estado inválido')
 with db() as c: c.execute('UPDATE orders SET status=?,paid=COALESCE(?,paid) WHERE id=?',(state,b.get('paid'),oid))
 return {'ok':True}
@app.get('/caja')
def cashier(u=Depends(admin)):
 body='<h1>Caja</h1><p>Pedidos y códigos de cuenta. Actualización automática.</p><div id="orders" class="grid"></div>'
 script="<script>async function load(){let r=await fetch('/api/orders?active=false');if(!r.ok)return;let a=await r.json();document.getElementById('orders').innerHTML=a.map(o=>'<section class=card><h2>#'+o.id+' · '+o.table_name+'</h2><p>Estado '+o.status+' · '+(o.total_cents/100).toFixed(2)+' €</p><p>Código de cuenta: <b>'+o.code+'</b></p><ul>'+o.items.map(i=>'<li>'+i.quantity+' × '+i.product_name+'</li>').join('')+'</ul><select id=s'+o.id+'>'+['nuevo','aceptado','preparacion','listo','servido'].map(s=>'<option '+(s===o.status?'selected':'')+'>'+s+'</option>').join('')+'</select> <button onclick=save('+o.id+')>Guardar estado</button> <button onclick=pay('+o.id+')>Marcar cobrado</button></section>').join('')||'Sin pedidos'}async function save(id){await fetch('/api/orders/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:document.getElementById('s'+id).value})});load()}async function pay(id){await fetch('/api/orders/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'servido',paid:true})});load()}load();setInterval(load,3000)</script>"
 return page('Caja',body,script)
@app.get('/cocina')
def kitchen(u=Depends(admin)):
 body='<h1>Cocina</h1><div id="orders" class="grid"></div>'; script="<script>async function load(){let r=await fetch('/api/orders');if(!r.ok)return;let a=await r.json();document.getElementById('orders').innerHTML=a.map(o=>'<section class=card><h2>#'+o.id+' · '+o.table_name+'</h2><p>'+o.status+'</p><ul>'+o.items.map(i=>'<li>'+i.quantity+' × '+i.product_name+'</li>').join('')+'</ul></section>').join('')||'Sin pedidos'}load();setInterval(load,3000)</script>"; return page('Cocina',body,script)
@app.get('/admin')
def admin_page(u=Depends(admin)):
 with db() as c: ps=c.execute('SELECT * FROM products ORDER BY category,name').fetchall(); ts=c.execute('SELECT * FROM tables ORDER BY id').fetchall()
 body='<h1>Administración</h1><section class=card><h2>Añadir producto</h2><form method=post action=/admin/product><input name=name placeholder=Nombre required><input name=category placeholder=Categoría value=Tapas><input name=price type=number step=.01 placeholder=Precio required><button>Guardar</button></form></section><section class=card><h2>Carta</h2><ul>'
 body+=''.join(f'<li>{p["name"]} — {money(p["price_cents"])} <a href="/admin/product/{p["id"]}/toggle">Cambiar disponibilidad</a></li>' for p in ps)+'</ul></section><section class=card><h2>Mesas y QR</h2><form method=post action=/admin/table><input name=name placeholder="Nombre mesa" required><button>Crear mesa</button></form><div class=grid>'
 body+=''.join(f'<section class=card><h3>{t["name"]}</h3><img width=140 src="/qr/{t["id"]}.png"><p><a href="/mesa/{t["id"]}">Abrir carta</a></p></section>' for t in ts)+'</div></section>'; return page('Administración',body)
@app.post('/admin/product')
async def add_product(request, u=Depends(admin)):
 f=await request.form()
 with db() as c: c.execute('INSERT INTO products(name,category,price_cents) VALUES(?,?,?)',(f['name'],f.get('category','Tapas'),round(float(f['price'])*100)))
 return RedirectResponse('/admin',status_code=303)
@app.get('/admin/product/{pid}/toggle')
def toggle_product(pid:int,u=Depends(admin)):
 with db() as c:c.execute('UPDATE products SET available=1-available WHERE id=?',(pid,))
 return RedirectResponse('/admin',status_code=303)
@app.post('/admin/table')
async def add_table(request,u=Depends(admin)):
 f=await request.form()
 with db() as c:c.execute('INSERT INTO tables(name) VALUES(?)',(f['name'],))
 return RedirectResponse('/admin',status_code=303)
@app.get('/qr/{tid}.png')
def qr(tid:int):
 with db() as c:t=c.execute('SELECT * FROM tables WHERE id=? AND active=1',(tid,)).fetchone()
 if not t: raise HTTPException(404,'Mesa no encontrada')
 out=io.BytesIO(); qrcode.make(f'{BASE}/mesa/{tid}').save(out,format='PNG'); out.seek(0); return StreamingResponse(out,media_type='image/png')
@app.get('/health')
def health(): return {'ok':True}
