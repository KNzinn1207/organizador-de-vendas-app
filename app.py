import os
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_super_segura'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Modelos do Banco de Dados Atualizados
class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  email = db.Column(db.String(150), unique=True, nullable=False)
  senha = db.Column(db.String(150), nullable=False)
  pedidos = db.relationship('Pedido', backref='autor', lazy=True)


class Pedido(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  nome_cliente = db.Column(db.String(100), nullable=False)
  produto = db.Column(db.String(100), nullable=False)
  horario = db.Column(db.String(50), nullable=False)
  valor = db.Column(db.String(50), nullable=False)
  status = db.Column(
      db.String(20), default='Pendente'
  )  # 'Pendente' ou 'Entregue'
  feedback = db.Column(db.Text, nullable=True)  # Comentário do cliente
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))


# Rotas de Autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    email = request.form.get('email')
    senha = request.form.get('senha')
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.senha, senha):
      login_user(user)
      return redirect(url_for('index'))
    else:
      flash('E-mail ou senha incorretos.', 'danger')
  return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    email = request.form.get('email')
    senha = request.form.get('senha')
    user_existente = User.query.filter_by(email=email).first()
    if user_existente:
      flash('Este e-mail já está cadastrado.', 'warning')
      return redirect(url_for('register'))

    novo_usuario = User(
        email=email, senha=generate_password_hash(senha, method='scrypt')
    )
    db.session.add(novo_usuario)
    db.session.commit()
    flash('Conta criada com sucesso! Faça login.', 'success')
    return redirect(url_for('login'))
  return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('login'))


# Rota Principal (Dashboard com Abas: Pedidos e Registros)
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
  if request.method == 'POST':
    nome_cliente = request.form.get('nome_cliente')
    produto = request.form.get('produto')
    horario = request.form.get('horario')
    valor = request.form.get('valor')

    if nome_cliente and produto and horario and valor:
      novo_pedido = Pedido(
          nome_cliente=nome_cliente,
          produto=produto,
          horario=horario,
          valor=valor,
          status='Pendente',
          user_id=current_user.id,
      )
      db.session.add(novo_pedido)
      db.session.commit()
      flash('Pedido cadastrado com sucesso!', 'success')

    return redirect(url_for('index'))

  # Separando os pedidos do usuário por status para as abas
  pedidos_pendentes = Pedido.query.filter_by(
      user_id=current_user.id, status='Pendente'
  ).all()
  pedidos_entregues = Pedido.query.filter_by(
      user_id=current_user.id, status='Entregue'
  ).all()
  todos_pedidos = Pedido.query.filter_by(user_id=current_user.id).all()

  return render_template(
      'index.html',
      pendentes=pedidos_pendentes,
      entregues=pedidos_entregues,
      todos=todos_pedidos,
  )


# Rota para Alternar Status (Marcar como Entregue)
@app.route('/alternar_status/<int:id>')
@login_required
def alternar_status(id):
  pedido = Pedido.query.get_or_404(id)
  if pedido.user_id == current_user.id:
    pedido.status = 'Entregue' if pedido.status == 'Pendente' else 'Pendente'
    db.session.commit()
  return redirect(url_for('index'))


# Rota para Salvar o Feedback
@app.route('/salvar_feedback/<int:id>', methods=['POST'])
@login_required
def salvar_feedback(id):
  pedido = Pedido.query.get_or_404(id)
  if pedido.user_id == current_user.id:
    pedido.feedback = request.form.get('feedback')
    db.session.commit()
    flash('Feedback registrado com sucesso!', 'success')
  return redirect(url_for('index'))


# Rota para Apagar Pedido
@app.route('/apagar/<int:id>')
@login_required
def apagar(id):
  pedido = Pedido.query.get_or_404(id)
  if pedido.user_id == current_user.id:
    db.session.delete(pedido)
    db.session.commit()
    flash('Pedido apagado com sucesso.', 'info')
  return redirect(url_for('index'))


if __name__ == '__main__':
  with app.app_context():
    db.create_all()
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port, debug=False)