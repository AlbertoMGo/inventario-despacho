from flask import Flask, render_template, redirect, url_for, request
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
import sqlite3, os

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

# Crear la base de datos si no existe
if not os.path.exists("inventario.db"):
    conn = sqlite3.connect("inventario.db")
    conn.execute("CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre TEXT, sucursal_a INT, sucursal_b INT, sucursal_c INT)")
    conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, password TEXT)")
    conn.execute("INSERT INTO users (id, password) VALUES ('admin', 'admin123')")
    conn.commit()

@app.route('/')
def index():
    conn = get_db()
    productos = conn.execute("SELECT * FROM productos").fetchall()
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

        elif accion in ['a_up', 'a_down', 'b_up', 'b_down', 'c_up', 'c_down']:
            producto_id = form['producto_id']
            producto = conn.execute("SELECT * FROM productos WHERE id=?", (producto_id,)).fetchone()
            a = producto['sucursal_a']
            b = producto['sucursal_b']
            c = producto['sucursal_c']

            match accion:
                case 'a_up': a += 1
                case 'a_down': a = max(0, a - 1)
                case 'b_up': b += 1
                case 'b_down': b = max(0, b - 1)
                case 'c_up': c += 1
                case 'c_down': c = max(0, c - 1)

            conn.execute("UPDATE productos SET sucursal_a=?, sucursal_b=?, sucursal_c=? WHERE id=?",
                         (a, b, c, producto_id))
            conn.commit()

        elif accion == 'guardar':
            producto_id = form['producto_id']
            a = int(form['a'])
            b = int(form['b'])
            c = int(form['c'])
            conn.execute("UPDATE productos SET sucursal_a=?, sucursal_b=?, sucursal_c=? WHERE id=?",
                         (a, b, c, producto_id))
            conn.commit()

        else:
            nombre = form['nombre']
            a = form['a']
            b = form['b']
            c = form['c']
            conn.execute("INSERT INTO productos (nombre, sucursal_a, sucursal_b, sucursal_c) VALUES (?, ?, ?, ?)",
                         (nombre, a, b, c))
            conn.commit()

    productos = conn.execute("SELECT * FROM productos").fetchall()
    return render_template("editar.html", productos=productos)

if __name__ == "__main__":
    app.run(debug=True)
