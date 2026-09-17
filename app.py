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

# Caminho seguro para escrita e armazenamento do SQLite no Render
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/database.db'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# 1. MODELOS DO BANCO DE DADOS
class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  email = db.Column(db.String(150), unique=True, nullable=False)
  senha = db.Column(db.String(150), nullable=False)
  ativo = db.Column(
      db.Boolean, default=False
  )  # False = Aguardando aprovação, True = Aprovado
  is_admin = db.Column(
      db.Boolean, default=False
  )  # True = Administrador do painel
  pedidos = db.relationship('Pedido', backref='autor', lazy=True)


class Pedido(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  nome_cliente = db.Column(db.String(100), nullable=False)
  telefone = db.Column(
      db.String(30), nullable=False
  )  # Novo campo de Telefone / WhatsApp
  produto = db.Column(db.String(100), nullable=False)
  horario = db.Column(db.String(50), nullable=False)
  valor = db.Column(db.String(50), nullable=False)
  status = db.Column(db.String(20), default='Pendente')
  feedback = db.Column(db.Text, nullable=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# 2. CRIAÇÃO DAS TABELAS
with app.app_context():
  db.create_all()


@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))


# Rota de Login com verificação de status
@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    email = request.form.get('email')
    senha = request.form.get('senha')
    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.senha, senha):
      if user.is_admin:
        login_user(user)
        return redirect(url_for('admin_painel'))

      if not user.ativo:
        return redirect(url_for('aguardando_aprovacao'))

      login_user(user)
      return redirect(url_for('index'))
    else:
      flash('E-mail ou senha incorretos.', 'danger')
  return render_template('login.html')


# Rota de Cadastro (O 1º usuário vira Admin e ativo automaticamente)
@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    email = request.form.get('email')
    senha = request.form.get('senha')
    user_existente = User.query.filter_by(email=email).first()

    if user_existente:
      flash('Este e-mail já está cadastrado.', 'warning')
      return redirect(url_for('register'))

    total_usuarios = User.query.count()
    primeiro_usuario = total_usuarios == 0

    novo_usuario = User(
        email=email,
        senha=generate_password_hash(senha),
        ativo=True if primeiro_usuario else False,
        is_admin=True if primeiro_usuario else False,
    )
    db.session.add(novo_usuario)
    db.session.commit()

    if primeiro_usuario:
      flash(
          'Conta Admin criada com sucesso! Você já está ativo.', 'success'
      )
    else:
      flash(
          'Cadastro realizado! Sua conta aguarda confirmação de pagamento/acesso.',
          'success',
      )

    return redirect(url_for('login'))
  return render_template('register.html')


# Página de aviso para contas pendentes
@app.route('/aguardando-aprovacao')
def aguardando_aprovacao():
  return render_template('aguardando.html')


# Painel Administrativo (Apenas para o Admin)
@app.route('/admin')
@login_required
def admin_painel():
  if not current_user.is_admin:
    flash('Acesso negado. Área restrita ao administrador.', 'danger')
    return redirect(url_for('index'))

  usuarios = User.query.all()
  return render_template('admin.html', usuarios=usuarios)


# Rota para o Admin aprovar o usuário
@app.route('/admin/aprovar/<int:id>')
@login_required
def aprovar_usuario(id):
  if not current_user.is_admin:
    flash('Acesso negado.', 'danger')
    return redirect(url_for('index'))

  user = User.query.get_or_404(id)
  user.ativo = True
  db.session.commit()
  flash(f'Usuário {user.email} aprovado com sucesso!', 'success')
  return redirect(url_for('admin_painel'))


@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('login'))


# Rota Principal (Dashboard do Cliente Aprovado)
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
  if current_user.is_admin:
    return redirect(url_for('admin_painel'))

  if request.method == 'POST':
    nome_cliente = request.form.get('nome_cliente')
    telefone = request.form.get('telefone')  # Capturando o telefone
    produto = request.form.get('produto')
    horario = request.form.get('horario')
    valor = request.form.get('valor')

    if nome_cliente and telefone and produto and horario and valor:
      novo_pedido = Pedido(
          nome_cliente=nome_cliente,
          telefone=telefone,
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


@app.route('/alternar_status/<int:id>')
@login_required
def alternar_status(id):
  pedido = Pedido.query.get_or_404(id)
  if pedido.user_id == current_user.id:
    pedido.status = 'Entregue' if pedido.status == 'Pendente' else 'Pendente'
    db.session.commit()
  return redirect(url_for('index'))


@app.route('/salvar_feedback/<int:id>', methods=['POST'])
@login_required
def salvar_feedback(id):
  pedido = Pedido.query.get_or_404(id)
  if pedido.user_id == current_user.id:
    pedido.feedback = request.form.get('feedback')
    db.session.commit()
    flash('Feedback registrado com sucesso!', 'success')
  return redirect(url_for('index'))


@app.route('/apagar/<int:id>')
@login_required
def apagar(id):
  pedido = Pedido.query.get_or_404(id)
  if pedido.user_id == current_user.id or current_user.is_admin:
    db.session.delete(pedido)
    db.session.commit()
    flash('Registro apagado com sucesso.', 'info')
  if current_user.is_admin:
    return redirect(url_for('admin_painel'))
  return redirect(url_for('index'))


if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port, debug=False)