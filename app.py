from flask import Flask, render_template, redirect, url_for, request, Response, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
import sqlite3, os, csv, io
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'inventario-secreto'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

def get_db():
    conn = sqlite3.connect("inventario.db")
    conn.row_factory = sqlite3.Row
    return conn

if not os.path.exists("inventario.db"):
    conn = get_db()
    conn.execute("""
        CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            unidad TEXT,
            stock_minimo INTEGER DEFAULT 0,
            ubicacion TEXT,
            sucursal_a INTEGER DEFAULT 0,
            sucursal_b INTEGER DEFAULT 0,
            sucursal_c INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, password TEXT)")
    conn.execute("INSERT INTO users (id, password) VALUES ('admin', 'admin123')")
    conn.commit()

@app.route('/')
def index():
    conn = get_db()
    productos = conn.execute("SELECT * FROM productos").fetchall()
    buscar = request.args.get('buscar', '').lower()
    ubicacion = request.args.get('ubicacion', '').lower()
    if buscar:
        productos = [p for p in productos if buscar in p["nombre"].lower()]
    if ubicacion:
        productos = [p for p in productos if ubicacion in (p["ubicacion"] or '').lower()]
    return render_template("index.html", productos=productos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['username']
        contraseña = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id=? AND password=?", (usuario, contraseña)).fetchone()
        if user:
            login_user(User(user["id"]))
            return redirect(url_for('editar'))
    return render_template("login.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/editar', methods=['GET', 'POST'])
@login_required
def editar():
    conn = get_db()
    if request.method == 'POST':
        form = request.form
        accion = form.get('accion')

        if accion == 'eliminar':
            producto_id = form['producto_id']
            conn.execute("DELETE FROM productos WHERE id=?", (producto_id,))
            conn.commit()

        elif accion == 'agregar':
            conn.execute("""
                INSERT INTO productos (nombre, unidad, stock_minimo, ubicacion, sucursal_a, sucursal_b, sucursal_c)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                form['nombre'],
                form['unidad'],
                int(form['stock_minimo']),
                form['ubicacion'],
                int(form['a']),
                int(form['b']),
                int(form['c'])
            ))
            conn.commit()

        elif accion == 'guardar_todos':
            productos_actualizados = []
            i = 0
            while True:
                producto_id = form.get(f'productos-{i}-id')
                if not producto_id:
                    break
                productos_actualizados.append((
                    form.get(f'productos-{i}-nombre'),
                    form.get(f'productos-{i}-unidad'),
                    int(form.get(f'productos-{i}-stock_minimo') or 0),
                    form.get(f'productos-{i}-ubicacion'),
                    int(form.get(f'productos-{i}-a') or 0),
                    int(form.get(f'productos-{i}-b') or 0),
                    int(form.get(f'productos-{i}-c') or 0),
                    int(producto_id)
                ))
                i += 1

            conn.executemany("""
                UPDATE productos
                SET nombre=?, unidad=?, stock_minimo=?, ubicacion=?, sucursal_a=?, sucursal_b=?, sucursal_c=?
                WHERE id=?
            """, productos_actualizados)
            conn.commit()

    productos = conn.execute("SELECT * FROM productos").fetchall()
    alertas = [p for p in productos if p["sucursal_a"] + p["sucursal_b"] + p["sucursal_c"] < p["stock_minimo"]]
    return render_template("editar.html", productos=productos, alertas=alertas)

@app.route('/exportar_csv')
@login_required
def exportar_csv():
    conn = get_db()
    productos = conn.execute("SELECT * FROM productos").fetchall()
    buscar = request.args.get('buscar', '').lower()
    sucursal = request.args.get('sucursal', '').lower()

    if buscar:
        productos = [p for p in productos if buscar in p["nombre"].lower()]
    if sucursal == 'a':
        productos = [p for p in productos if p["sucursal_a"] > 0]
    elif sucursal == 'b':
        productos = [p for p in productos if p["sucursal_b"] > 0]
    elif sucursal == 'c':
        productos = [p for p in productos if p["sucursal_c"] > 0]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nombre', 'Unidad', 'Stock Mínimo', 'Ubicación', 'Sucursal A', 'Sucursal B', 'Sucursal C'])

    for p in productos:
        writer.writerow([
            p['id'], p['nombre'], p['unidad'], p['stock_minimo'], p['ubicacion'],
            p['sucursal_a'], p['sucursal_b'], p['sucursal_c']
        ])

    output.seek(0)
    return Response(output, mimetype='text/csv', headers={
        "Content-Disposition": "attachment; filename=inventario.csv"
    })

@app.route('/exportar-excel')
def exportar_excel():
    conn = get_db()
    productos = conn.execute("SELECT * FROM productos").fetchall()

    # Aplicar mismos filtros que en la página pública
    buscar = request.args.get('buscar', '').lower()
    ubicacion = request.args.get('ubicacion', '').lower()

    if buscar:
        productos = [p for p in productos if buscar in p["nombre"].lower()]
    if ubicacion:
        productos = [p for p in productos if ubicacion in (p["ubicacion"] or '').lower()]

    # Crear DataFrame
    data = [{
        'Producto': p['nombre'],
        'Unidad': p['unidad'],
        'Stock mínimo': p['stock_minimo'],
        'Ubicación': p['ubicacion'],
        'Sucursal A': p['sucursal_a'],
        'Sucursal B': p['sucursal_b'],
        'Sucursal C': p['sucursal_c']
    } for p in productos]

    df = pd.DataFrame(data)

    # Generar archivo Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario')
    output.seek(0)

    return send_file(output, download_name="inventario.xlsx", as_attachment=True)

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=10000)
