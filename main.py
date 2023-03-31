from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from forms import CreatePostForm, CreateUserForm, LoginForm, CommentForm
from flask_gravatar import Gravatar


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

# #CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)

# Gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


def admin_only(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        if current_user.id != 1:
            abort(403)
        return func(*args, **kwargs)
    return decorator


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# CONFIGURE TABLES
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="commenter")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = relationship("User", back_populates="posts")
    author_id = db.mapped_column(db.ForeignKey("user.id"))
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="blog")


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blog = relationship("BlogPost", back_populates="comments")
    blog_id = db.mapped_column(db.ForeignKey("blog_posts.id"))
    commenter = relationship("User", back_populates="comments")
    commenter_id = db.mapped_column(db.ForeignKey("user.id"))
    content = db.Column(db.Text, nullable=False)


# # Create tables
# with app.app_context():
#     db.create_all()


@app.route('/users')
def users():
    user_objects = db.session.execute(db.select(User).order_by(User.name)).scalars()
    for user in user_objects:
        print(user.email)
    return f"<p>{db.session.execute(db.select(User)).scalars()}</p>"


@app.route('/')
def get_all_posts():
    posts = db.session.execute(db.select(BlogPost)).scalars().all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["POST", "GET"])
def register():
    form = CreateUserForm()
    if form.validate_on_submit():
        email = request.form['email']
        existing_user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if existing_user:
            flash("Email already registered, please login instead.")
            return redirect(url_for('login'))
        name = request.form['name']
        password = generate_password_hash(password=request.form['password'],
                                          method="pbkdf2:sha256",
                                          salt_length=8)
        user = User(name=name, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('get_all_posts'))
    else:
        return render_template("register.html", form=form)


@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = request.form['email']
        password = request.form['password']
        user_object = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user_object:
            if check_password_hash(pwhash=user_object.password, password=password):
                login_user(user_object)
                return redirect(url_for('get_all_posts'))
            else:  # Password is incorrect
                flash("Credentials are invalid. Please try again.")
        else:  # User does not exist
            flash("Credentials are invalid. Please try again.")
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    comment_form = CommentForm()
    blog = BlogPost.query.get(post_id)
    if comment_form.validate_on_submit():
        if current_user.is_active:
            content = comment_form.comment.data
            comment = Comment(content=content,
                              commenter=current_user,
                              blog=blog)
            db.session.add(comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id))
        else:
            flash("Only logged in users are able to comment.")
            return redirect(url_for('show_post', post_id=post_id))
    comments = db.session.execute(db.select(Comment)).scalars()
    return render_template("post.html", post=blog, comment_form=comment_form, comments=comments)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["POST", "GET"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
